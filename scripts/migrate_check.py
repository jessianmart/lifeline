"""Prova a migração SEM tocar no arquivo vivo: ingere a LIFELINE.md real, gera a
markdown a partir do store, re-ingere e confirma que os ids são estáveis (ponto fixo).
Mostra um trecho do formato novo para inspeção antes da virada definitiva.
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lifeline.store import SQLiteEventStore        # noqa: E402
from lifeline.ingest import ingest_markdown, ingest_text  # noqa: E402
from lifeline.projection import render_ledger_markdown    # noqa: E402


async def main():
    here = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(os.path.dirname(here), "LIFELINE.md")
    tmp = tempfile.mkdtemp()

    # 1. Migração: markdown antigo (prev_hash) -> store (ids content-addressed novos)
    s1 = SQLiteEventStore(os.path.join(tmp, "1.db"))
    await s1.initialize()
    n1 = await ingest_markdown(md_path, s1)
    ids1 = [e.id async for e in s1.stream()]

    # 2. store -> markdown gerada
    generated = await render_ledger_markdown(s1)

    # 3. markdown gerada -> store2 -> markdown de novo (deve ser ponto fixo)
    s2 = SQLiteEventStore(os.path.join(tmp, "2.db"))
    await s2.initialize()
    n2 = await ingest_text(generated, s2)
    ids2 = [e.id async for e in s2.stream()]
    generated2 = await render_ledger_markdown(s2)

    print("=" * 72)
    print(f"Migração: {n1} entradas ingeridas do markdown antigo.")
    print(f"Re-ingestão da markdown gerada: {n2} entradas.")
    print(f"[{'PASS' if ids1 == ids2 else 'FALHA'}] ids estáveis (ponto fixo)")
    print(f"[{'PASS' if generated == generated2 else 'FALHA'}] markdown byte-idêntica no 2º render")
    print("=" * 72)
    print("AMOSTRA do formato gerado (primeira entrada):\n")
    print("\n".join(generated.splitlines()[:16]))
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
