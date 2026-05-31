"""CLI do Lifeline — o store é a fonte de verdade; a LIFELINE.md é uma view gerada.

    lifeline log --kind decision --summary "…" --body "…"   # humano: anexa direto (você é o aprovador)
    lifeline propose --kind … --summary … --body …          # propõe (HITL) — entra pendente, não na line
    lifeline review                                         # lista pendências (curadoria)
    lifeline approve <pid|all> | reject <pid|all>           # HITL: sela ou descarta
    lifeline context [--query "…"] | verify | rebuild | migrate --from … | lines

Tiering (como aprovar comando shell): humano no `log` = commit direto; IA via MCP = `propose`
(pendente até um humano aprovar). Multi-line: `--line <nome>` → .lifeline/<nome>.db + LIFELINE.<nome>.md.
"""
import argparse
import asyncio
import glob
import json
import os
import sys

from lifeline import sync
from lifeline.entry import Entry, KINDS
from lifeline.store import SQLiteEventStore
from lifeline.staging import SQLiteStagingStore
from lifeline.ingest import ingest_markdown, _parse_ts
from lifeline.projection import render_ledger_markdown
from lifeline.state import StateEngine
from lifeline.context import ContextAssembler

DEFAULT_DB = os.environ.get("LIFELINE_DB", os.path.join(".lifeline", "ledger.db"))
DEFAULT_OUT = "LIFELINE.md"
LINES_DIR = ".lifeline"

# Store ativo, escolhido por main() via --store (default: SQLite local). Fica aqui para o
# seam _open() trocar de adapter sem reescrever cada comando. Resetado a cada main().
_STORE = {"kind": "sqlite", "line": "ledger"}
# Comandos que só fazem sentido no store local (git e glob de .db). O HITL
# (propose/review/approve/reject) já funciona na nuvem via SupabaseStagingStore.
_LOCAL_ONLY = {"push", "pull", "clone", "lines"}

PREAMBLE = """# LIFELINE — lifeline

> Cadeia append-only de *porquês*. O projeto guarda *por que* ele é o que é, e qualquer
> mente que conecta herda esse porquê na hora — sem ninguém reexplicar.
>
> **Este arquivo é GERADO** a partir do ledger (em `.lifeline/`), que é a fonte de verdade.
> NÃO edite à mão — anexe com `lifeline log` e ele se regenera.
>
> **Comece pela #0001.** Ela é o projeto inteiro em linguagem humana.

## Protocolo

1. **Append-only.** Nunca edite entradas; uma correção é uma entrada nova (`kind: correction`)
   que referencia em `parents` o `id` que corrige — e o supersede na verdade atual.
2. **Uma entrada por unidade de trabalho com significado.** Não por arquivo, não por tool
   call. O *porquê* pesa mais que o *quê* (Lei #5).
3. **Identidade content-addressed (Lei #3):** `id = sha256(kind, author, agent, provider,
   model, summary, body, parents-ordenados)`. `ts` e `dedup_key` ficam FORA do hash — o
   mesmo conteúdo gera o mesmo `id` em qualquer máquina. `parents` formam o DAG causal;
   não há prev_hash (o ledger é um grafo, não uma lista).
4. **Integridade:** `lifeline verify` confere que todo `id` bate com seu conteúdo.
5. **Anexar:** `lifeline log --kind … --summary … --body …`. Ver o contexto montado que uma
   IA receberia: `lifeline context`.

## Leis do projeto (a constituição)

1. **Nenhuma memória sem âncora imutável.** Todo item de contexto carrega o hash do evento
   de origem. Espinha anti-alucinação.
2. **Append-only.** Correções são entradas novas referenciando o id anterior.
3. **Content-addressing determinístico.** Mesmo conteúdo+pais → mesmo id, em qualquer nó.
4. **Storage agnóstico de provider; entrega no formato do provider.**
5. **O *porquê* pesa mais que o *quê*.**
6. **Budget é first-class.** Contexto cabe na janela; truncamento é explícito, nunca silencioso.
7. **MCP-native.** A interface da IA é a superfície do produto, não um apêndice.

**Non-goals (lei por omissão):** Lifeline NÃO é sistema operacional cognitivo, NÃO é MMU,
NÃO é orquestrador/sandbox de agentes, NÃO é workflow engine, NÃO substitui git, NÃO é
executor/curador (self-healing) nem treinador (fine-tuning/DL). Registra raciocínio.

---"""


def resolve_paths(line, db, out):
    """Resolve (db, out) a partir de --line (açúcar) ou dos flags explícitos.
    `--line NAME` mapeia ledger E view juntos, sem colisão entre lines."""
    if line:
        return os.path.join(LINES_DIR, f"{line}.db"), f"LIFELINE.{line}.md"
    return db, out


async def _open(db):
    if _STORE["kind"] == "supabase":
        from lifeline.cloud import SupabaseEventStore  # lazy: só puxa httpx no modo nuvem
        s = SupabaseEventStore(line=_STORE["line"])     # lê SUPABASE_URL/KEY do ambiente
        await s.initialize()
        return s
    os.makedirs(os.path.dirname(db) or ".", exist_ok=True)
    s = SQLiteEventStore(db)
    await s.initialize()
    return s


def _staging(db):
    """Fila HITL no backend ativo (espelha _open). Nuvem usa SupabaseStagingStore."""
    if _STORE["kind"] == "supabase":
        from lifeline.cloud import SupabaseStagingStore
        return SupabaseStagingStore(line=_STORE["line"])
    os.makedirs(os.path.dirname(db) or ".", exist_ok=True)
    return SQLiteStagingStore(db)


async def _head_id(store):
    last = None
    async for e in store.stream():
        last = e
    return last.id if last else None


async def _write_view(store, out):
    md = await render_ledger_markdown(store, PREAMBLE)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    n = 0
    async for _ in store.stream():
        n += 1
    return n


def _validate(kind, body):
    """Anti-sujeira no write-time: kind válido + o *porquê* presente (Lei #5)."""
    if kind not in KINDS:
        raise ValueError(f"kind inválido '{kind}'. Use um de: {', '.join(KINDS)}")
    if not (body and body.strip()):
        raise ValueError("falta o *porquê* em --body (Lei #5: o porquê pesa mais que o quê).")


async def cmd_log(db, out, kind, summary, body, author, agent, provider, model, parents):
    store = await _open(db)
    if parents is None:
        head = await _head_id(store)
        parents = [head] if head else []
    e = Entry(kind=kind, author=author, agent=agent, provider=provider,
              model=model, summary=summary, body=body or "", parents=parents)
    inserted = await store.append(e)
    n = await _write_view(store, out)
    return e, inserted, n


async def cmd_propose(db, kind, summary, body, author, agent, provider, model, parents):
    """Enfileira uma proposta (HITL). Async/leve: não toca na line, não regenera a view."""
    _validate(kind, body)
    staging = _staging(db)
    await staging.initialize()
    return await staging.propose(kind=kind, summary=summary, body=body, author=author,
                                 agent=agent, provider=provider, model=model, parents=parents)


async def cmd_review(db):
    staging = _staging(db)
    await staging.initialize()
    return await staging.pending()


async def cmd_approve(db, out, pids):
    staging = _staging(db)
    await staging.initialize()
    store = await _open(db)
    targets = await staging.pending() if pids == ["all"] else [await staging.get(int(p)) for p in pids]
    approved = 0
    for prop in targets:
        if not prop or prop["status"] != "pending":
            continue
        head = await _head_id(store)
        stored = json.loads(prop["parents"]) if prop.get("parents") else []
        parents = stored or ([head] if head else [])
        kw = dict(kind=prop["kind"], author=prop["author"], agent=prop["agent"],
                  provider=prop["provider"], model=prop["model"], summary=prop["summary"],
                  body=prop["body"] or "", parents=parents)
        ts = _parse_ts(prop["ts"])           # preserva o momento da decisão (capture-at-start)
        if ts is not None:
            kw["ts"] = ts
        await store.append(Entry(**kw))
        await staging.set_status(prop["pid"], "approved")
        approved += 1
    n = await _write_view(store, out) if approved else 0
    return approved, n


async def cmd_reject(db, pids):
    staging = _staging(db)
    await staging.initialize()
    ids = [p["pid"] for p in await staging.pending()] if pids == ["all"] else [int(p) for p in pids]
    for pid in ids:
        await staging.set_status(pid, "rejected")
    return len(ids)


async def cmd_rebuild(db, out):
    store = await _open(db)
    return await _write_view(store, out)


async def cmd_verify(db):
    store = await _open(db)
    ok, n = True, 0
    async for e in store.stream():
        n += 1
        if not e.verify():
            ok = False
    return ok, n


async def cmd_migrate(src, db):
    store = await _open(db)
    return await ingest_markdown(src, store)


async def cmd_context(db, budget, query=None):
    store = await _open(db)
    recall = None
    if query:
        from lifeline.recall import SemanticRecall
        recall = SemanticRecall(store)
    return await ContextAssembler(StateEngine(store), budget_chars=budget).assemble(query=query, recall=recall)


async def cmd_lines(root=LINES_DIR):
    rows = []
    for path in sorted(glob.glob(os.path.join(root, "*.db"))):
        name = os.path.splitext(os.path.basename(path))[0]
        store = SQLiteEventStore(path)
        await store.initialize()
        n = 0
        async for _ in store.stream():
            n += 1
        rows.append((name, n))
    return rows


async def cmd_push(db, out, message="lifeline: sync"):
    if not sync.is_repo():
        raise ValueError("não é um repositório git aqui. Faça: git init && git remote add origin <url>")
    await cmd_rebuild(db, out)                  # garante a view textual atual
    sync.add_commit(".", message)               # ok se não houver nada a commitar
    r = sync.push(".")
    return r.returncode == 0, (r.stderr or r.stdout).strip()


async def cmd_pull(db, out):
    if not sync.is_repo():
        raise ValueError("não é um repositório git aqui.")
    r = sync.pull(".")
    if sync.has_conflict():
        return False, "CONFLITO de merge na view — resolva no LIFELINE.md (é legível) e rode pull de novo."
    await cmd_migrate(out, db)                   # ingere o markdown mergeado (dedup por id)
    await cmd_rebuild(db, out)                   # normaliza a view a partir do .db unido
    return r.returncode == 0, (r.stderr or r.stdout).strip()


async def cmd_clone(url, dest):
    r = sync.clone(url, dest)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    src = os.path.join(dest, DEFAULT_OUT)
    if os.path.exists(src):                      # reconstrói o .db a partir da view clonada
        db = os.path.join(dest, LINES_DIR, "ledger.db")
        await cmd_migrate(src, db)
        await cmd_rebuild(db, src)
    return True, f"clonado em {dest} (.db reconstruído da view)"


def _parents_arg(s):
    return [x.strip() for x in s.split(",") if x.strip()] if s else None


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # UTF-8 em console legado (Windows cp1252)
    except Exception:
        pass

    p = argparse.ArgumentParser(prog="lifeline", description="Lifeline — runtime de contexto")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--line", default=None, help="nome da line (sugar: .lifeline/<line>.db + LIFELINE.<line>.md)")
    p.add_argument("--store", choices=["sqlite", "supabase"], default="sqlite",
                   help="backend do ledger (M3 Tier 1: supabase lê SUPABASE_URL/KEY do ambiente)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def _entry_args(sp, with_out=False):
        sp.add_argument("--kind", required=True)
        sp.add_argument("--summary", required=True)
        sp.add_argument("--body", default="")
        sp.add_argument("--author", default=os.environ.get("LIFELINE_AUTHOR", "unknown"))
        sp.add_argument("--agent", default="human")
        sp.add_argument("--provider", default="none")
        sp.add_argument("--model", default="human")
        sp.add_argument("--parents", default=None, help="ids separados por vírgula")
        if with_out:
            sp.add_argument("--out", default=DEFAULT_OUT)

    _entry_args(sub.add_parser("log", help="humano: anexa direto na line (você é o aprovador)"), with_out=True)
    _entry_args(sub.add_parser("propose", help="propõe uma entrada (HITL) — fica pendente até aprovar"))

    sub.add_parser("review", help="lista as propostas pendentes (curadoria HITL)")
    pa = sub.add_parser("approve", help="sela proposta(s) pendente(s) na line")
    pa.add_argument("pids", nargs="+", help="pids a aprovar, ou 'all'")
    prj = sub.add_parser("reject", help="descarta proposta(s) pendente(s)")
    prj.add_argument("pids", nargs="+", help="pids a rejeitar, ou 'all'")

    pr = sub.add_parser("rebuild", help="regenera a view a partir do store")
    pr.add_argument("--out", default=DEFAULT_OUT)
    sub.add_parser("verify", help="confere a integridade do ledger")
    pm = sub.add_parser("migrate", help="ingere uma markdown antiga no store")
    pm.add_argument("--from", dest="src", required=True)
    pc = sub.add_parser("context", help="imprime o contexto montado")
    pc.add_argument("--budget", type=int, default=8000)
    pc.add_argument("--query", default=None, help="prioriza o que é relevante à tarefa (Camada 3)")
    sub.add_parser("lines", help="lista as lines do projeto (.lifeline/*.db)")

    ppush = sub.add_parser("push", help="sync via git: rebuild + commit + push da view")
    ppush.add_argument("--out", default=DEFAULT_OUT)
    ppull = sub.add_parser("pull", help="sync via git: pull + reconstrói o .db da view mergeada")
    ppull.add_argument("--out", default=DEFAULT_OUT)
    pclone = sub.add_parser("clone", help="git clone <url> <dir> e reconstrói o .db")
    pclone.add_argument("url")
    pclone.add_argument("dest")

    args = p.parse_args(argv)
    db, out = resolve_paths(args.line, args.db, getattr(args, "out", DEFAULT_OUT))

    _STORE["kind"] = args.store                  # reset explícito a cada chamada (sem vazar entre runs)
    _STORE["line"] = args.line or "ledger"
    if args.store == "supabase" and args.cmd in _LOCAL_ONLY:
        print(f"'{args.cmd}' é específico do store local (git/HITL/SQLite). "
              f"Com --store supabase use: log, context, verify, rebuild, migrate.")
        return 1

    if args.cmd == "log":
        e, inserted, n = asyncio.run(cmd_log(
            db, out, args.kind, args.summary, args.body, args.author, args.agent,
            args.provider, args.model, _parents_arg(args.parents)))
        print(f"#{n:04d} {'registrada' if inserted else 'duplicada (idempotente)'}: {e.kind} — {e.id[:12]}…")
        print(f"{out} regenerado ({n} entradas).")
        return 0

    if args.cmd == "propose":
        try:
            pid = asyncio.run(cmd_propose(db, args.kind, args.summary, args.body, args.author,
                                          args.agent, args.provider, args.model, _parents_arg(args.parents)))
        except ValueError as ex:
            print(f"recusado: {ex}")
            return 1
        print(f"proposta #{pid} enfileirada (PENDENTE). Curadoria: lifeline review")
        return 0

    if args.cmd == "review":
        rows = asyncio.run(cmd_review(db))
        if not rows:
            print("Nenhuma proposta pendente.")
            return 0
        print(f"{len(rows)} proposta(s) pendente(s) (HITL):\n")
        for r in rows:
            print(f"  #{r['pid']} [{r['kind']}] {r['summary']}  — por {r['provider']}/{r['model']}")
            if r["body"]:
                s = r["body"].strip().replace("\n", " ")
                print(f"        {s[:160] + ('…' if len(s) > 160 else '')}")
        print("\nAprovar: lifeline approve <pid|all>    ·    Rejeitar: lifeline reject <pid|all>")
        return 0

    if args.cmd == "approve":
        approved, n = asyncio.run(cmd_approve(db, out, args.pids))
        if approved:
            print(f"{approved} proposta(s) aprovada(s) e seladas na line. {out} regenerado ({n} entradas).")
        else:
            print("Nada aprovado (pids inválidos ou sem pendências).")
        return 0

    if args.cmd == "reject":
        print(f"{asyncio.run(cmd_reject(db, args.pids))} proposta(s) rejeitada(s).")
        return 0

    if args.cmd == "rebuild":
        print(f"{out} regenerado ({asyncio.run(cmd_rebuild(db, out))} entradas).")
        return 0

    if args.cmd == "verify":
        ok, n = asyncio.run(cmd_verify(db))
        print(f"{'OK' if ok else 'BROKEN'}: {n} entradas {'íntegras' if ok else 'COM FALHA'}.")
        return 0 if ok else 1

    if args.cmd == "migrate":
        n = asyncio.run(cmd_migrate(args.src, db))
        print(f"Migradas {n} entradas de {args.src} para {db}.")
        return 0

    if args.cmd == "context":
        print(asyncio.run(cmd_context(db, args.budget, args.query)))
        return 0

    if args.cmd == "lines":
        rows = asyncio.run(cmd_lines())
        if not rows:
            print("Nenhuma line ainda. Crie com: lifeline log [--line <nome>] --kind … --summary …")
            return 0
        for name, n in rows:
            label = f"{name} (default)" if name == "ledger" else name
            view = "LIFELINE.md" if name == "ledger" else f"LIFELINE.{name}.md"
            print(f"  {label:<22} {n:>4} entradas   → {view}")
        return 0

    if args.cmd == "push":
        try:
            ok, msg = asyncio.run(cmd_push(db, out))
        except ValueError as ex:
            print(f"erro: {ex}")
            return 1
        print(("push OK — line sincronizada. " if ok else "push falhou: ") + msg)
        return 0 if ok else 1

    if args.cmd == "pull":
        try:
            ok, msg = asyncio.run(cmd_pull(db, out))
        except ValueError as ex:
            print(f"erro: {ex}")
            return 1
        print(("pull OK — .db reconstruído da view mergeada. " if ok else "") + msg)
        return 0 if ok else 1

    if args.cmd == "clone":
        ok, msg = asyncio.run(cmd_clone(args.url, args.dest))
        print(msg)
        return 0 if ok else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
