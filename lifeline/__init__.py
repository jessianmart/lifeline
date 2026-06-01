"""Lifeline — runtime de contexto. O projeto guarda *por que* ele é o que é."""
from lifeline.entry import Entry, GENESIS
from lifeline.store import EventStore, SQLiteEventStore
from lifeline.state import StateEngine, ledger_projection
from lifeline.context import ContextAssembler
from lifeline.recall import (
    Embedder, LexicalEmbedder, SentenceTransformerEmbedder, SemanticRecall, make_embedder,
)
from lifeline.staging import StagingStore, SQLiteStagingStore

__version__ = "0.2.0"
__all__ = [
    "Entry", "GENESIS",
    "EventStore", "SQLiteEventStore",
    "StateEngine", "ledger_projection",
    "ContextAssembler",
    "Embedder", "LexicalEmbedder", "SentenceTransformerEmbedder", "SemanticRecall", "make_embedder",
    "StagingStore", "SQLiteStagingStore",
]
