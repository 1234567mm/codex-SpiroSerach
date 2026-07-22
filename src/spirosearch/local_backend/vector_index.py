"""Optional vector index adapter seam for the V33C local backend."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class VectorIndex(Protocol):
    """Minimal embedding index contract.

    The first V33C slice keeps embeddings optional.  Concrete adapters can
    satisfy this protocol without changing SQLite repositories or read APIs.
    """

    def upsert(self, chunk_id: str, embedding: Sequence[float]) -> str:
        ...

    def search(self, embedding: Sequence[float], *, limit: int = 10) -> tuple[dict[str, object], ...]:
        ...


@dataclass(frozen=True)
class NoopVectorIndex:
    """Disabled vector index implementation used until embeddings are enabled."""

    status: str = "not_configured"

    def upsert(self, chunk_id: str, embedding: Sequence[float]) -> str:
        return self.status

    def search(self, embedding: Sequence[float], *, limit: int = 10) -> tuple[dict[str, object], ...]:
        return ()
