"""Projeção store → markdown. Inverte a relação: o store é a fonte de verdade; a
LIFELINE.md vira uma VIEW gerada (como o payload de contexto, mas a render completa).

Cada entrada mostra seu `id` content-addressed (o hash unificado) e seus `parents` —
não mais o prev_hash do esquema markdown antigo. Render + ingest formam um ponto fixo:
store → markdown → store reproduz exatamente os mesmos ids (prova de fidelidade).
"""
from typing import List

from lifeline.entry import Entry
from lifeline.store import EventStore

# Sentinela de FIM de entrada (gap #G6). O ingester fatiava por `^### #`, então um body que
# CITASSE uma entrada (`### #0002 — …`) ou terminasse em `---` era cortado e seu id mudava no
# clone/pull — round-trip não-lossless, quebrando o content-addressing de que tudo depende. Um
# comentário HTML é invisível no markdown renderizado (diffável) e dá um limite inequívoco: o
# corpo é tudo entre `**Body**:` e a sentinela, recuperado byte-a-byte.
BODY_END = "<!-- lifeline:end -->"


def render_entry(n: int, e: Entry) -> str:
    parents = ", ".join(e.parents) if e.parents else "—"
    return (
        f"### #{n:04d} — {e.ts.isoformat()} — {e.kind}\n\n"
        f"- **author**: {e.author}\n"
        f"- **agent**: {e.agent}\n"
        f"- **provider**: {e.provider}\n"
        f"- **model**: {e.model}\n"
        f"- **kind**: {e.kind}\n"
        f"- **summary**: {e.summary}\n"
        f"- **parents**: {parents}\n"
        f"- **id**: {e.id}\n\n"
        f"**Body**:\n{e.body}\n\n{BODY_END}\n"
    )


def render_entries(entries: List[Entry]) -> str:
    return "\n".join(render_entry(i + 1, e) for i, e in enumerate(entries))


async def render_ledger_markdown(store: EventStore, preamble: str = "") -> str:
    entries = [e async for e in store.stream()]
    head = (preamble.rstrip() + "\n\n## Entries\n\n") if preamble else "## Entries\n\n"
    return head + render_entries(entries)
