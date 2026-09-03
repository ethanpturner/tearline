"""Qdrant, where isolation is application-supplied (DEC-018).

**Enforcement site: the application.** Multi-tenancy is a payload field with a tenant index, or
per-tenant sharding. The store filters on the value it is handed and has no notion of who is asking.

Qdrant's JWT support restricts *which collection* a key may touch and whether it may write. It does
not bind a tenant: nothing injects `tenant == <claim>` into a query. Qdrant's own multi-tenancy
guidance says isolation relies on the application layer, and qdrant#8015 -- open since 2026-01-30 --
is a request for the binding that does not exist. A claim that "Qdrant enforces tenant isolation via
JWT" is inaccurate as commonly stated.

So everything DEC-017 leaves to the engine is in scope here, and `retrieve_unfiltered` exists to
demonstrate it: the same query without the application's filter returns other tenants' points,
correctly and quickly. That is not a defect in Qdrant. It is where the boundary lives.

Uses the HTTP API through the standard library rather than a client package: the API surface needed
here is two endpoints, and a verification tool earns little by adding a dependency for them.

**This adapter issues no write.** Creating the collection and loading points belongs to the test
harness (`tests/live/harness.py`), not to the tool: DEC-004 says the tool does not create test
documents, and an adapter carrying a `DELETE /collections/...` is one mistaken argument away from
doing it to a production index.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from tearline.backends.base import RetrievalRequest
from tearline.domain import Chunk, Entitlement, EntitlementState

COLLECTION = "tearline_chunks"
DIMENSIONS = 16

#: The only payload keys this adapter asks for. Requesting the whole payload would pull chunk text
#: into the tool's memory wherever an index stores it alongside the metadata -- and DEC-002's rule
#: is that the tool does not read content, not merely that it does not print it. Naming the fields
#: keeps that true against an index whose payload the tool did not design.
PAYLOAD_FIELDS = [
    "chunk_id",
    "source_document_ids",
    "entitlement_state",
    "tenants",
    "roles",
    "principals",
    "ingested_at",
]


class QdrantBackend:
    """Reads points and issues retrievals, with the tenant filter supplied by this code."""

    enforcement_site = "application"

    def __init__(self, base_url: str, collection: str = COLLECTION, timeout: float = 15.0) -> None:
        self._base = base_url.rstrip("/")
        self._collection = collection
        self._timeout = timeout

    # -- transport -----------------------------------------------------------------------

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self._base}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read()[:200]!r}") from exc

    # -- the Backend protocol ------------------------------------------------------------

    def chunks(self) -> list[Chunk]:
        """Every point as stored. No privilege is required, which is itself the finding: anything
        able to reach the collection can read all of it."""
        result = self._request(
            "POST",
            f"/collections/{self._collection}/points/scroll",
            {"limit": 1000, "with_payload": PAYLOAD_FIELDS},
        )
        out: list[Chunk] = []
        for point in result["result"]["points"]:
            payload = point["payload"]
            out.append(
                Chunk(
                    id=payload["chunk_id"],
                    source_document_ids=tuple(payload.get("source_document_ids") or ()),
                    entitlement=Entitlement(
                        state=EntitlementState(payload["entitlement_state"]),
                        tenants=frozenset(payload.get("tenants") or ()),
                        roles=frozenset(payload.get("roles") or ()),
                        principals=frozenset(payload.get("principals") or ()),
                    ),
                    ingested_at=(
                        datetime.fromisoformat(payload["ingested_at"])
                        if payload.get("ingested_at")
                        else None
                    ),
                )
            )
        return sorted(out, key=lambda c: c.id)

    def retrieve(self, request: RetrievalRequest) -> list[str]:
        """Chunk ids for this principal, with the tenant filter supplied by this method.

        The filter is written here, in application code, and nothing in the store requires it. That
        is the whole difference from DEC-017: forget this clause and the query still succeeds.
        """
        body: dict[str, Any] = {
            "vector": list(request.vector),
            "limit": request.limit,
            "with_payload": ["chunk_id"],
            "filter": {"must": [{"key": "tenants", "match": {"value": request.principal.tenant}}]},
        }
        result = self._request("POST", f"/collections/{self._collection}/points/search", body)
        return [point["payload"]["chunk_id"] for point in result["result"]]

    def retrieve_unfiltered(self, request: RetrievalRequest) -> list[str]:
        """The same query with the filter omitted.

        Not a convenience. It is the demonstration that the boundary is application-supplied: this
        returns other tenants' points, correctly and quickly, and no configuration of the store
        prevents it. On the engine-enforced backend the equivalent query returns nothing extra.
        """
        result = self._request(
            "POST",
            f"/collections/{self._collection}/points/search",
            {"vector": list(request.vector), "limit": request.limit, "with_payload": ["chunk_id"]},
        )
        return [point["payload"]["chunk_id"] for point in result["result"]]
