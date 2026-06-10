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
    dicts esparsos; um denso usaria listas. A similaridade é definida pelo embedder.

    `min_score` é o piso de ABSTENÇÃO (gap #G5): um hit só conta se a similaridade for
    ESTRITAMENTE maior que ele. No lexical (TF esparso) 0.0 já abstém de fato — sem token
    compartilhado dá 0 exato. No denso o cosseno entre dois textos quaisquer é quase sempre
    > 0, então 0.0 NUNCA abstém e reintroduz match espúrio; por isso o denso sobe esse piso."""
    name: str
    min_score: float = 0.0

    @abstractmethod
    def embed(self, text: str) -> Any: ...

    @abstractmethod
    def similarity(self, a: Any, b: Any) -> float: ...


class LexicalEmbedder(Embedder):
    """Term-frequency esparso, L2-normalizado. Cosseno exato; sem colisão. Default local."""

    def __init__(self):
        self.name = "lexical-tf"
        self.min_score = 0.0  # sem sobreposição → 0 exato; o piso 0 já abstém honestamente

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

    def __init__(self, model: str = "all-MiniLM-L6-v2", _model: Any = None,
                 min_score: Optional[float] = None):
        self.name = f"st:{model}"
        self._model_name = model
        self._m = _model  # injetável p/ teste (evita baixar o modelo)
        # piso de abstenção do denso (gap #G5): cosseno denso quase nunca é ≤ 0, então 0.0
        # não filtraria ruído. Default 0.3, ajustável por LIFELINE_RECALL_MIN_SCORE.
        if min_score is None:
            try:
                min_score = float(os.environ.get("LIFELINE_RECALL_MIN_SCORE", "0.3"))
            except ValueError:
                min_score = 0.3
        self.min_score = min_score

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

    async def search(self, query: str, k: int = 5,
                     superseded: Optional[set] = None) -> List[Dict]:
        """Retorna os k mais relevantes acima do piso de abstenção do embedder (gap #G5).
        `superseded` (opcional): marca cada hit revertido com `superseded=True` (gap #G2) —
        sem isso, o recall serve decisão morta como viva. A verdade segue ancorada: o hit
        carrega o id do evento; o status é metadado derivado, não reescreve o passado."""
        if not self._records:
            await self.index()
        sup = superseded or set()
        floor = getattr(self.embedder, "min_score", 0.0)
        q = self.embedder.embed(query)
        scored = []
        for r in self._records:
            s = self.embedder.similarity(q, r["vector"])
            if s > floor:  # abaixo do piso → não é relevante (não inventa match)
                scored.append({"id": r["id"], "summary": r["summary"], "kind": r["kind"],
                               "score": round(s, 4), "superseded": r["id"] in sup})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]
