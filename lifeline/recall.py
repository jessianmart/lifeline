"""Camada 3 — recall associativo ANCORADO. Cada embedding é só um índice que aponta
para um evento imutável (Lei #1); a verdade é a entrada, não o vetor — então errar o
match não vira alucinação, só um retrieval pior.

`Embedder` é a costura (decisão #0015): plugável, um modelo por índice. O default é o
`LexicalEmbedder` — term-frequency esparso, cosseno EXATO sobre tokens compartilhados,
determinístico e SEM dependência. (Tentamos hashing primeiro; o teste pegou colisão de
buckets gerando falsa relevância — daí o TF esparso, que dá 0 exato sem sobreposição.)
Um embedder semântico denso (sentence-transformers / API) pluga atrás da mesma interface.
"""
import math
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from lifeline.store import EventStore

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


class Embedder(ABC):
    """Embeda texto e mede similaridade. O formato do embedding é opaco — lexical usa
    dicts esparsos; um denso usaria listas. A similaridade é definida pelo embedder."""
    name: str

    @abstractmethod
    def embed(self, text: str) -> Any: ...

    @abstractmethod
    def similarity(self, a: Any, b: Any) -> float: ...


class LexicalEmbedder(Embedder):
    """Term-frequency esparso, L2-normalizado. Cosseno exato; sem colisão. Default local."""

    def __init__(self):
        self.name = "lexical-tf"

    def embed(self, text: str) -> Dict[str, float]:
        counts: Dict[str, float] = {}
        for tok in _tokens(text):
            counts[tok] = counts.get(tok, 0.0) + 1.0
        norm = math.sqrt(sum(v * v for v in counts.values()))
        return {t: v / norm for t, v in counts.items()} if norm else {}

    def similarity(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(w * b.get(t, 0.0) for t, w in a.items())


class SentenceTransformerEmbedder(Embedder):
    """Embedder semântico DENSO (opcional, #0029): casa por SIGNIFICADO, não por palavra.
    Lazy-import de sentence-transformers (extra `lifeline-context[embeddings]`) — o default do
    projeto segue sendo o LexicalEmbedder (zero-dep). Vetores normalizados → similaridade = cosseno."""

    def __init__(self, model: str = "all-MiniLM-L6-v2", _model: Any = None):
        self.name = f"st:{model}"
        self._model_name = model
        self._m = _model  # injetável p/ teste (evita baixar o modelo)

    def _ensure(self):
        if self._m is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "embedder denso precisa do extra: pip install 'lifeline-context[embeddings]'"
                ) from e
            self._m = SentenceTransformer(self._model_name)
        return self._m

    def embed(self, text: str) -> List[float]:
        v = self._ensure().encode(text or "", normalize_embeddings=True)
        return [float(x) for x in v]

    def similarity(self, a: List[float], b: List[float]) -> float:
        return float(sum(x * y for x, y in zip(a, b)))  # cosseno (vetores já normalizados)


def make_embedder(spec: Optional[str] = None) -> Embedder:
    """Escolhe o embedder por `spec` ou pela env LIFELINE_EMBEDDER. Default/'lexical' →
    LexicalEmbedder (zero-dep). 'dense' → SentenceTransformerEmbedder (modelo default); qualquer
    outro valor é tratado como nome de modelo sentence-transformers (ex.: 'all-mpnet-base-v2')."""
    spec = (spec or os.environ.get("LIFELINE_EMBEDDER") or "lexical").strip()
    if spec in ("lexical", "tf", ""):
        return LexicalEmbedder()
    if spec == "dense":
        return SentenceTransformerEmbedder()
    return SentenceTransformerEmbedder(model=spec)


class SemanticRecall:
    """Indexa as entradas do ledger e recupera as mais relevantes a uma query — ancoradas."""

    def __init__(self, store: EventStore, embedder: Optional[Embedder] = None):
        self.store = store
        self.embedder = embedder or LexicalEmbedder()
        self._records: List[Dict] = []  # {id, vector, summary, kind}

    async def index(self) -> int:
        self._records = []
        async for e in self.store.stream():
            vec = self.embedder.embed(f"{e.summary}\n{e.body}")
            self._records.append({"id": e.id, "vector": vec, "summary": e.summary, "kind": e.kind})
        return len(self._records)

    async def search(self, query: str, k: int = 5) -> List[Dict]:
        if not self._records:
            await self.index()
        q = self.embedder.embed(query)
        scored = []
        for r in self._records:
            s = self.embedder.similarity(q, r["vector"])
            if s > 0.0:  # sem sobreposição → não é relevante (não inventa match)
                scored.append({"id": r["id"], "summary": r["summary"],
                               "kind": r["kind"], "score": round(s, 4)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]
