"""The backend seam."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tearline.domain import Chunk, Principal


@dataclass(frozen=True)
class RetrievalRequest:
    """What a probe asks a backend for.

    `vector` is supplied rather than computed. Relevance is not under test (DEC-011), and requiring
    an embedding model to check an entitlement boundary would make the tool depend on the very
    component whose output it is trying not to judge.
    """

    vector: Sequence[float]
    principal: Principal
    limit: int


def deterministic_vector(text: str, dimensions: int) -> list[float]:
    """A stable pseudo-embedding, so fixtures and live runs use the same query for the same text.

    It carries no semantics and is not meant to. Two texts that mean the same thing get unrelated
    vectors, which would be fatal for a relevance tool and is irrelevant here: the question is which
    chunks a principal is *permitted* to receive, and that must not depend on what the query meant.
    """
    digest = hashlib.sha256(text.encode()).digest()
    raw = (digest * (dimensions // len(digest) + 1))[:dimensions]
    # Centre on zero so the vectors are not all in one orthant.
    return [(byte - 127.5) / 127.5 for byte in raw]


@runtime_checkable
class Backend(Protocol):
    """What an adapter must provide.

    `runtime_checkable` so `issubclass` works, which is what makes the protocol load-bearing rather
    than decorative -- `tests/unit/test_backends.py` checks both adapters against it. The check is
    structural and shallow: it sees the names, not the signatures.

    Deliberately two methods. `chunks()` supports the propagation and drift axes, which compare
    stored entitlements against the source system. `retrieve()` supports the differential axis,
    which is the only one that can observe whether the boundary is actually applied.
    """

    #: Where isolation is enforced: "engine" or "application". Reported with every result, because
    #: the same verdict means different things on the two (DEC-010).
    enforcement_site: str

    def chunks(self) -> list[Chunk]:
        """Every chunk in the index, with the entitlement metadata as stored."""
        ...

    def retrieve(self, request: RetrievalRequest) -> list[str]:
        """Chunk ids returned for this principal. Ids only, never content (DEC-002)."""
        ...
