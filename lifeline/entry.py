"""O Entry — a unidade atômica da linha de vida.

Content-addressed e determinístico (Lei #3): `id = sha256(conteúdo + pais)`.
`ts` e `dedup_key` são metadados e ficam FORA do hash, para que o mesmo conteúdo
gere o mesmo id em qualquer máquina ou momento — pré-requisito para dedup e merge
entre nós/usuários no futuro.
"""
import hashlib
from datetime import datetime, timezone
from typing import List, Literal, Optional, get_args

from pydantic import BaseModel, Field, model_validator

GENESIS = hashlib.sha256(b"GENESIS").hexdigest()

Kind = Literal[
    "bootstrap", "decision", "feature", "fix",
    "incident", "milestone", "release", "note", "open", "correction"
]

KINDS = get_args(Kind)  # tupla dos kinds válidos — usada pra validar propostas (anti-sujeira)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Entry(BaseModel):
    """Um registro imutável da cadeia de raciocínio do projeto."""

    model_config = {"strict": True}

    id: str = ""                                   # derivado (content-addressed)
    ts: datetime = Field(default_factory=utcnow)   # metadado — FORA do hash
    kind: Kind
    author: str
    agent: str = "human"
    provider: str = "none"
    model: str = "human"
    summary: str                                   # o *quê* (≤200 por convenção)
    body: str = ""                                 # o *porquê* (pesa mais)
    parents: List[str] = Field(default_factory=list)
    dedup_key: Optional[str] = None                # idempotência — FORA do hash

    def _canonical(self) -> str:
        """Forma canônica determinística. Pais ordenados → id invariante à ordem."""
        fields = [
            self.kind, self.author, self.agent, self.provider,
            self.model, self.summary, self.body.strip(),
        ]
        return "\n".join(fields) + "\n" + "|".join(sorted(self.parents)) + "\n"

    def compute_id(self) -> str:
        return hashlib.sha256(self._canonical().encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def _seal(self) -> "Entry":
        # Sela o id a partir do conteúdo+pais, se ainda não veio do storage.
        if not self.id:
            self.id = self.compute_id()
        return self

    def verify(self) -> bool:
        """True se o id ainda bate com o conteúdo (não foi adulterado)."""
        return self.id == self.compute_id()
