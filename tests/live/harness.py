"""Building a live index to verify against. Not part of the tool.

Everything here writes, which is why none of it is in `src/`. DEC-004 makes `tearline` read-only
against every system it touches -- it does not create test documents, provision identities, or
modify a policy to observe the effect -- and that guarantee is worth more as a structural fact than
as a promise: an adapter that carries a `TRUNCATE` is read-only only until somebody calls it.

So the fixtures below stand up the index these tests then verify, in the same repository and out of
the shipped package. `tests/unit/test_backends.py` asserts the separation holds.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from tearline.backends.pgvector import PRINCIPAL_SETTING
from tearline.backends.qdrant import DIMENSIONS, QdrantBackend
from tearline.domain import Chunk

if TYPE_CHECKING:  # pragma: no cover - typing only
    from psycopg import Connection

SCHEMA = (
    """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id                  text PRIMARY KEY,
    source_document_ids text[] NOT NULL DEFAULT '{}',
    ingested_at         timestamptz,
    entitlement_state   text NOT NULL,
    tenants             text[] NOT NULL DEFAULT '{}',
    roles               text[] NOT NULL DEFAULT '{}',
    principals          text[] NOT NULL DEFAULT '{}',
    embedding           vector(16)
);

ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
-- Applies to the table owner too. Without this the owner bypasses the policy and a test run as the
-- owner would observe perfect isolation that no other role has.
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chunk_tenant_isolation ON chunks;
CREATE POLICY chunk_tenant_isolation ON chunks
    FOR SELECT
    USING (
        -- An empty tenant array is NOT a grant (DEC-003). The policy is written so absence
        -- excludes rather than admits, which is the failure `untagged-chunk` exists for.
        cardinality(tenants) > 0
        AND current_setting('"""
    + PRINCIPAL_SETTING
    + """', true) = ANY (tenants)
    );
"""
)


def apply_pgvector_schema(connection: Connection[Any]) -> None:
    """Create the table and the policy. Privileged: CREATE EXTENSION is not available to a
    principal's role, which is the same asymmetry the adapter's two connections encode."""
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA)
    connection.commit()


def load_pgvector(
    connection: Connection[Any], chunks: Sequence[tuple[Chunk, Sequence[float]]]
) -> None:
    """Replace the table's contents. The policy governs SELECT, not writes."""
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE chunks")
        for chunk, vector in chunks:
            cursor.execute(
                """
                INSERT INTO chunks (id, source_document_ids, ingested_at, entitlement_state,
                                    tenants, roles, principals, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    chunk.id,
                    list(chunk.source_document_ids),
                    chunk.ingested_at,
                    chunk.entitlement.state.value,
                    sorted(chunk.entitlement.tenants),
                    sorted(chunk.entitlement.roles),
                    sorted(chunk.entitlement.principals),
                    str(list(vector)),
                ),
            )
    connection.commit()


def apply_qdrant_schema(backend: QdrantBackend, collection: str) -> None:
    backend._request("DELETE", f"/collections/{collection}")
    backend._request(
        "PUT",
        f"/collections/{collection}",
        {"vectors": {"size": DIMENSIONS, "distance": "Cosine"}},
    )
    # A tenant index is what makes payload filtering efficient. It is an optimisation and not a
    # boundary: the filter still has to be supplied by the caller.
    backend._request(
        "PUT",
        f"/collections/{collection}/index?wait=true",
        {"field_name": "tenants", "field_schema": "keyword"},
    )


def load_qdrant(
    backend: QdrantBackend, collection: str, chunks: Sequence[tuple[Chunk, Sequence[float]]]
) -> None:
    points = [
        {
            "id": index + 1,
            "vector": list(vector),
            "payload": {
                "chunk_id": chunk.id,
                "source_document_ids": list(chunk.source_document_ids),
                "entitlement_state": chunk.entitlement.state.value,
                "tenants": sorted(chunk.entitlement.tenants),
                "roles": sorted(chunk.entitlement.roles),
                "principals": sorted(chunk.entitlement.principals),
                "ingested_at": chunk.ingested_at.isoformat() if chunk.ingested_at else None,
            },
        }
        for index, (chunk, vector) in enumerate(chunks)
    ]
    backend._request("PUT", f"/collections/{collection}/points?wait=true", {"points": points})
