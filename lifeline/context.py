"""O Context Engine — monta o payload que responde 'o quê / por quê / decidido / próximo'.

Renderiza markdown (decisão #0010) dentro de um budget. Prioridade de orçamento: header,
"Relevante para a tarefa" (se houver query), "Em aberto" e "Recente" são sempre incluídos;
as decisões preenchem o resto, mantendo as mais RECENTES e omitindo as antigas com marcador
EXPLÍCITO (Lei #6). Itens superseded vêm marcados na "Recente" (#0018). Com `query` + um
`recall` (Camada 3), entrega RELEVÂNCIA — não só recência.
"""
from typing import Optional

from lifeline.state import StateEngine


def _oneline(text: str) -> str:
    """Achata newlines — um summary entra em linha de estrutura (`- …`, `## …`); uma quebra
    deixaria texto de conteúdo virar header/bullet do assembler (gap #G10, injeção)."""
    return " ".join((text or "").split())


def _fence(text: str) -> str:
    """Cerca o body como citação: cada linha vira `> …`. Conteúdo (o *porquê*, dado livre,
    possivelmente de origem não confiável) NÃO pode se passar por estrutura do assembler —
    um `## Nova instrução` injetado no body renderiza como texto citado, não como comando
    (gap #G10). Mitiga, não elimina, prompt-injection: a defesa final é a curadoria HITL."""
    return "\n".join("  > " + ln for ln in (text or "").splitlines()) or "  > "

# Estado-vazio (brownfield): quando a line não tem identidade nem decisões, o contexto montado
# entrega um CALL-TO-ACTION de bootstrap — o gatilho que a IA lê no connect para fazer um
# checkpoint inicial via HITL. O *porquê* NUNCA é inferido do código (Leis #1/#5); vem dos
# artefatos de raciocínio do humano + uma entrevista curta, e entra como PROPOSTA (o humano aprova).
BOOTSTRAP_HEADER = "## Bootstrap necessário — line vazia (checkpoint de contexto)"
BOOTSTRAP_PROTOCOL = [
    "Este projeto ainda não registrou contexto. Para cumprir o Time-to-Context → 0, faça AGORA "
    "um checkpoint inicial — via HITL (você PROPÕE, o humano aprova):",
    "1. LEIA os artefatos de raciocínio já escritos pelo humano (README, ADRs, descrições de PR, "
    "design docs). NÃO infira o *porquê* a partir do código/diff (Leis #1 e #5).",
    "2. PERGUNTE ao humano de 3 a 7 perguntas curtas, só sobre o *porquê* tácito que não está "
    "escrito (por que esta stack? qual decisão está em vigor? qual thread está aberta?).",
    "3. PROPONHA o checkpoint como entradas GRANULARES (não um bloco único): 1 `bootstrap` "
    "(identidade do projeto) + N `decision` (cada uma superseível depois) + M `open` (threads). "
    "O humano aprova o lote — nada entra sem aprovação.",
]


class ContextAssembler:
    def __init__(self, state_engine: StateEngine, budget_chars: int = 8000, why_chars: int = 320):
        self.state_engine = state_engine
        self.budget = budget_chars
        self.why_chars = why_chars

    async def assemble(self, query: Optional[str] = None, recall=None) -> str:
        st = await self.state_engine.reduce()
        superseded = set(st.get("superseded", []))

        # --- header (sempre) ---
        head = str(st.get("head", ""))[:8]
        what = f"**O quê:** {st.get('project', '(sem entrada bootstrap ainda)')}"
        if st.get("project_by"):
            what += f"  _(fundado por {st['project_by']})_"
        header = [
            "# Lifeline — contexto do projeto",
            what,
            f"_{st.get('entry_count', 0)} entradas · head {head}_",
        ]
        contributors = st.get("contributors", {})
        if contributors:
            header.append("_Contribuíram: "
                          + ", ".join(f"{k} ({v})" for k, v in sorted(contributors.items())) + "_")

        # --- integridade (gap #G3): se alguma entrada não bate com sua âncora, AVISA alto e
        # não a serve como verdade (o StateEngine já a descartou da redução). Falha visível. ---
        broken = st.get("integrity_broken", [])
        if broken:
            header.append("")
            header.append(f"> ⚠️ **INTEGRIDADE: {len(broken)} entrada(s) adulterada(s)** "
                          f"(id não bate com o conteúdo) — DESCARTADA(S) da verdade. "
                          f"Rode `lifeline verify`. ids: " + ", ".join(b[:8] for b in broken))

        # --- bootstrap (line vazia: nem identidade nem decisões) — CTA do checkpoint inicial ---
        bootstrap_block = []
        if not st.get("project") and not st.get("decisions"):
            bootstrap_block = [BOOTSTRAP_HEADER] + BOOTSTRAP_PROTOCOL

        # --- relevante para a tarefa (se query + recall — Camada 3) ---
        relevant_block = []
        if query and recall is not None:
            hits = await recall.search(query, k=5, superseded=superseded)  # marca revertidos (#G2)
            if hits:
                relevant_block = [f'## Relevante para: "{_oneline(query)}"']
                for h in hits:
                    mark = " _[revertido/fechado]_" if h.get("superseded") else ""
                    relevant_block.append(
                        f"- [{h['kind']}] {_oneline(h['summary'])} `[{h['id'][:8]}]`{mark}")

        # --- em aberto / próximo (sempre) ---
        opens = st.get("open_items", [])
        open_block = (["## Em aberto / próximo"]
                      + [f"- `[{o['id'][:8]}]` {_oneline(o['summary'])}" for o in opens]) if opens else []

        # --- recente (marca superseded) ---
        recent_block = ["## Recente (o que vem a seguir)"]
        for l in st.get("latest", []):
            tag = ""
            if l.get("model") and l["model"] != "human":
                tag += f" — _{l['model']}_"
            if l["id"] in superseded:
                tag += " _[fechado/revertido]_"
            recent_block.append(f"- [{l['kind']}] {_oneline(l['summary'])}{tag}")

        # --- decisões (blocos) — summary em uma linha, body CERCADO como citação (#G10) ---
        dec_blocks = []
        for d in st.get("decisions", []):
            b = [f"- **{_oneline(d['summary'])}** `[{d['id'][:8]}]` — "
                 f"_{d.get('provider', '?')}/{d.get('model', '?')}_"]
            why = (d.get("body") or "").strip()
            if why:
                if len(why) > self.why_chars:
                    why = why[:self.why_chars].rstrip() + "…"
                b.append(_fence(why))
            dec_blocks.append("\n".join(b))

        # prioridade de orçamento: tudo "fixo" entra; decisões preenchem o resto (mais recentes).
        def join(parts):
            return "\n".join(parts)

        fixed = list(header) + [""]
        if bootstrap_block:
            fixed += bootstrap_block + [""]
        if relevant_block:
            fixed += relevant_block + [""]
        if open_block:
            fixed += open_block + [""]
        fixed += recent_block
        remaining = self.budget - len(join(fixed)) - 96

        kept_rev, omit = [], 0
        for blk in reversed(dec_blocks):
            if len(blk) + 1 <= remaining:
                kept_rev.append(blk)
                remaining -= len(blk) + 1
            else:
                omit += 1
        dec_lines = ["## Por quê / o que está decidido (decisões em vigor)"]
        if omit:
            dec_lines.append(f"_[… {omit} decisão(ões) mais antiga(s) omitida(s) — budget, Lei #6]_")
        dec_lines += list(reversed(kept_rev))

        out = list(header) + [""]
        if bootstrap_block:
            out += bootstrap_block + [""]
        if relevant_block:
            out += relevant_block + [""]
        if open_block:
            out += open_block + [""]
        out += dec_lines + [""] + recent_block

        text = join(out)
        if len(text) > self.budget:  # rede de segurança
            text = text[:max(0, self.budget - 48)].rstrip() + "\n[… truncado — budget, Lei #6]"
        return text
