"""O Context Engine — monta o payload que responde 'o quê / por quê / decidido / próximo'.

Renderiza markdown (decisão #0010) dentro de um budget. Prioridade de orçamento: header,
"Relevante para a tarefa" (se houver query), "Em aberto" e "Recente" são sempre incluídos;
as decisões preenchem o resto, mantendo as mais RECENTES e omitindo as antigas com marcador
EXPLÍCITO (Lei #6). Itens superseded vêm marcados na "Recente" (#0018). Com `query` + um
`recall` (Camada 3), entrega RELEVÂNCIA — não só recência.
"""
from typing import Optional

from lifeline.state import StateEngine


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

        # --- relevante para a tarefa (se query + recall — Camada 3) ---
        relevant_block = []
        if query and recall is not None:
            hits = await recall.search(query, k=5)
            if hits:
                relevant_block = [f'## Relevante para: "{query}"']
                relevant_block += [f"- [{h['kind']}] {h['summary']} `[{h['id'][:8]}]`" for h in hits]

        # --- em aberto / próximo (sempre) ---
        opens = st.get("open_items", [])
        open_block = (["## Em aberto / próximo"]
                      + [f"- `[{o['id'][:8]}]` {o['summary']}" for o in opens]) if opens else []

        # --- recente (marca superseded) ---
        recent_block = ["## Recente (o que vem a seguir)"]
        for l in st.get("latest", []):
            tag = ""
            if l.get("model") and l["model"] != "human":
                tag += f" — _{l['model']}_"
            if l["id"] in superseded:
                tag += " _[fechado/revertido]_"
            recent_block.append(f"- [{l['kind']}] {l['summary']}{tag}")

        # --- decisões (blocos) ---
        dec_blocks = []
        for d in st.get("decisions", []):
            b = [f"- **{d['summary']}** `[{d['id'][:8]}]` — _{d.get('provider', '?')}/{d.get('model', '?')}_"]
            why = (d.get("body") or "").strip()
            if why:
                if len(why) > self.why_chars:
                    why = why[:self.why_chars].rstrip() + "…"
                b.append(f"  > {why}")
            dec_blocks.append("\n".join(b))

        # prioridade de orçamento: tudo "fixo" entra; decisões preenchem o resto (mais recentes).
        def join(parts):
            return "\n".join(parts)

        fixed = list(header) + [""]
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
        if relevant_block:
            out += relevant_block + [""]
        if open_block:
            out += open_block + [""]
        out += dec_lines + [""] + recent_block

        text = join(out)
        if len(text) > self.budget:  # rede de segurança
            text = text[:max(0, self.budget - 48)].rstrip() + "\n[… truncado — budget, Lei #6]"
        return text
