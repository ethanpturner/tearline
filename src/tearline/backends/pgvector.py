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


class BypassesRowSecurity(RuntimeError):
    """The connected role is not subject to row-level security."""


class PgVectorBackend:
    """Reads chunks and issues retrievals as a principal, letting the engine enforce."""

    enforcement_site = "engine"

    def __init__(
        self,
        connection: Connection[Any],
        *,
        admin_connection: Connection[Any] | None = None,
    ) -> None:
        """Two connections, because the two axes need opposite privileges.

        `connection` issues retrievals as a principal and **must be subject to** row-level
        security, or the differential axis observes an artifact of the connection rather than a
        property of the policy.

        `admin_connection` reads the whole index for the propagation axis and **must be able to
        bypass** it, because comparing what the index holds against the source system means seeing
        rows no principal can see -- which is exactly the population where a mislabelling hides.

        Needing both is not an inconvenience of the adapter; it is what an audit of this backend
        actually requires, and a single-connection design would silently do one of the two badly.
        """
        self._connection = connection
        self._admin = admin_connection
        self.assert_subject_to_row_security()

    def assert_subject_to_row_security(self) -> None:
        """Refuse to verify through a role that bypasses the policy.

        **Found by the first live CI run, which reported perfect isolation for a policy that was
        not being applied.** A superuser bypasses row-level security entirely, and
        `FORCE ROW LEVEL SECURITY` does not change that -- FORCE binds the table *owner*, not a
        superuser. So a connection as `postgres` sees every row, every retrieval looks correctly
        filtered because the caller only asked for their own tenant's data anyway, and the tool
        reports that the boundary holds.

        That is the worst failure this adapter could have: not a wrong answer, but a confident
        right-looking answer produced by never testing the thing under test. The check costs one
        query and is on by default; `allow_bypass` exists only for the propagation axis, which
        reads with row security deliberately off.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
            row = cursor.fetchone()
        self._connection.rollback()
        if row is None:
            raise BypassesRowSecurity(
                f"cannot determine the privileges of {self._connection.info.user!r}"
            )
        if row[0]:
            raise BypassesRowSecurity(
                "the connected role bypasses row-level security (superuser or BYPASSRLS), so any "
                "isolation this adapter appears to observe would be an artifact of the connection "
                "rather than a property of the policy. Connect as an unprivileged role."
            )

    # -- setup ---------------------------------------------------------------------------

    def apply_schema(self) -> None:
        """Requires the admin connection: CREATE EXTENSION is privileged."""
        connection = self._admin or self._connection
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA)
        connection.commit()

    def load(self, chunks: Sequence[tuple[Chunk, Sequence[float]]]) -> None:
        """Insert chunks through the admin connection; the policy governs SELECT, not writes."""
        connection = self._admin or self._connection
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

    # -- the Backend protocol ------------------------------------------------------------

    def chunks(self) -> list[Chunk]:
        """Every chunk as stored, read through the admin connection.

        The propagation axis compares what the index *holds* against the source system, and a
        policy-filtered read would only ever show rows some principal can already see -- precisely
        the population where a mislabelling is invisible.
        """
        if self._admin is None:
            raise BypassesRowSecurity(
                "reading every chunk requires a connection that can bypass row-level security, and "
                "none was supplied. The propagation axis cannot run through a principal's "
                "connection: it would only ever see rows that principal is already permitted, which "
                "is the one population where a mislabelled chunk cannot be detected."
            )
        with self._admin.cursor() as cursor:
            cursor.execute("SET LOCAL row_security = off")
            cursor.execute(
                "SELECT id, source_document_ids, ingested_at, entitlement_state, tenants, roles,"
                " principals FROM chunks ORDER BY id"
            )
            rows = cursor.fetchall()
        self._admin.rollback()
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
