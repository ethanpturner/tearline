"""PostgreSQL with `pgvector` and row-level security (DEC-017).

**Enforcement site: the engine.** A row-level security policy is evaluated by the database, so an
application that forgets its `WHERE` clause still cannot read another tenant's rows. The boundary
does not depend on the retrieval code being correct.

That is exactly why this adapter is interesting rather than redundant. Engine enforcement guarantees
the policy is *applied*; it guarantees nothing about whether the policy expresses the source
system's ACL. Propagation faults and drift live entirely in how a chunk's tenant column was
populated at ingestion, which RLS never inspects -- it enforces the stored value faithfully.

The residual risk it does carry is **completeness**: with an approximate index, entitlement
filtering runs after the ANN scan unless a supporting index lets the planner push it down, so a
selective policy can return fewer matches than exist. Confidentiality holds and completeness breaks
silently, which is `post-filter-truncation` occurring natively rather than as a bug.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from tearline.backends.base import RetrievalRequest
from tearline.domain import Chunk, Entitlement, EntitlementState

if TYPE_CHECKING:  # pragma: no cover - typing only
    from psycopg import Connection

# The session variable an RLS policy reads to identify the caller. Set per statement rather than
# per connection so a pooled connection cannot carry one principal's identity into another's query.
PRINCIPAL_SETTING = "tearline.principal_tenant"

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


class PgVectorBackend:
    """Reads chunks and issues retrievals as a principal, letting the engine enforce."""

    enforcement_site = "engine"

    def __init__(self, connection: Connection[Any]) -> None:
        self._connection = connection

    # -- setup ---------------------------------------------------------------------------

    def apply_schema(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(SCHEMA)
        self._connection.commit()

    def load(self, chunks: Sequence[tuple[Chunk, Sequence[float]]]) -> None:
        """Insert chunks. Runs as the owner with the policy temporarily bypassed for writes only."""
        with self._connection.cursor() as cursor:
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
        self._connection.commit()

    # -- the Backend protocol ------------------------------------------------------------

    def chunks(self) -> list[Chunk]:
        """Every chunk as stored.

        Read with the policy bypassed: the propagation axis compares what the index *holds* against
        the source system, and a policy-filtered read would only ever show rows some principal can
        already see -- which is precisely the population where a mislabelling is invisible.
        """
        with self._connection.cursor() as cursor:
            cursor.execute("SET LOCAL row_security = off")
            cursor.execute(
                "SELECT id, source_document_ids, ingested_at, entitlement_state, tenants, roles,"
                " principals FROM chunks ORDER BY id"
            )
            rows = cursor.fetchall()
        self._connection.rollback()
        return [
            Chunk(
                id=row[0],
                source_document_ids=tuple(row[1] or ()),
                ingested_at=row[2],
                entitlement=Entitlement(
                    state=EntitlementState(row[3]),
                    tenants=frozenset(row[4] or ()),
                    roles=frozenset(row[5] or ()),
                    principals=frozenset(row[6] or ()),
                ),
            )
            for row in rows
        ]

    def retrieve(self, request: RetrievalRequest) -> list[str]:
        """Chunk ids the engine returns for this principal. Ids only, never content (DEC-002)."""
        tenant = request.principal.tenant or ""
        with self._connection.cursor() as cursor:
            # `set_config(..., is_local => true)` is the parameterised equivalent of SET LOCAL:
            # PostgreSQL does not accept a placeholder in a SET statement, and interpolating the
            # tenant into the SQL string would put caller-supplied text into a statement, which is
            # not a trade worth making in a tool that exists to check access boundaries.
            #
            # `is_local` scopes the identity to this transaction, so a pooled connection cannot
            # carry one principal's identity into another principal's query.
            cursor.execute("SELECT set_config(%s, %s, true)", (PRINCIPAL_SETTING, tenant))
            cursor.execute(
                "SELECT id FROM chunks ORDER BY embedding <-> %s::vector LIMIT %s",
                (str(list(request.vector)), request.limit),
            )
            ids = [row[0] for row in cursor.fetchall()]
        self._connection.rollback()
        return ids
