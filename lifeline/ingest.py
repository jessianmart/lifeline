"""Ingester: lê uma LIFELINE.md (markdown) e carrega os entries no ledger (store).

Lossless: preserva ts e parents quando presentes. Para markdown no formato antigo
(prev_hash, sem campo `parents`) encadeia linearmente (single-writer). Para markdown
GERADO pelo store (com `parents` e `id` explícitos) reconstrói o DAG exato — base do
round-trip estável que torna o store a fonte de verdade e a markdown uma projeção.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from lifeline.entry import Entry
from lifeline.projection import BODY_END
from lifeline.store import EventStore


def _parse_ts(s: str):
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _blocks(text: str) -> List[str]:
    """Fatia o markdown em blocos-de-entrada. Formato NOVO (com a sentinela BODY_END): corta
    por ela — robusto a `### #`/`---` DENTRO do body (gap #G6). Formato LEGADO (sem sentinela):
    cai no fatiamento por `^### #` (compatível com markdowns antigas)."""
    if BODY_END in text:
        out = []
        for seg in text.split(BODY_END):
            i = seg.find("### #")
            if i != -1:
                out.append(seg[i:])
        return out
    return ["### #" + part for part in re.split(r"(?m)^### #", text)[1:]]


def parse_markdown(text: str) -> List[Dict]:
    legacy = BODY_END not in text
    out = []
    for block in _blocks(text):
        header = re.match(r"### #(\d+)\s+—\s+(\S+)\s+—\s+(\w+)", block)
        if not header:
            continue

        def field(name):
            m = re.search(rf"(?m)^- \*\*{name}\*\*:\s*(.*)$", block)
            return m.group(1).strip() if m else ""

        bm = re.search(r"\*\*Body\*\*:\s*\n(.*)", block, re.S)
        # Formato novo: o corpo é tudo até a sentinela (já removida pelo split) → só .strip()
        # (que casa com o `body.strip()` do hash, Lei #3). Legado: mantém o antigo corte de `---`.
        if bm:
            body = bm.group(1)
            if legacy:
                body = re.sub(r"\n*---\s*$", "", body)
            body = body.strip()
        else:
            body = ""

        parents_raw = field("parents")
        parents = ([] if parents_raw in ("", "—", "-")
                   else [p.strip() for p in parents_raw.split(",") if p.strip()])

        out.append({
            "ts": header.group(2),
            "kind": header.group(3),
            "author": field("author"),
            "agent": field("agent") or "human",
            "provider": field("provider") or "none",
            "model": field("model") or "human",
            "summary": field("summary"),
            "body": body,
            "parents": parents,
            "recorded_id": field("id") or field("hash"),
        })
    return out


async def ingest_text(text: str, store: EventStore) -> int:
    prev_id = None
    count = 0
    for d in parse_markdown(text):
        parents = d["parents"] if d["parents"] else ([prev_id] if prev_id else [])
        kwargs = dict(
            kind=d["kind"], author=d["author"], agent=d["agent"],
            provider=d["provider"], model=d["model"],
            summary=d["summary"], body=d["body"], parents=parents,
        )
        ts = _parse_ts(d["ts"])
        if ts is not None:
            kwargs["ts"] = ts
        entry = Entry(**kwargs)
        if await store.append(entry):
            count += 1
        prev_id = entry.id
    return count


async def ingest_markdown(path: str, store: EventStore) -> int:
    return await ingest_text(Path(path).read_text(encoding="utf-8"), store)
