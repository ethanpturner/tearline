"""The pgvector + RLS backend, against a real PostgreSQL.

Deselected by default (`-m "not live"` in addopts). CI runs them against a `pgvector/pgvector`
service container; there is no local Postgres, so this is where the adapter is actually verified.

Run with: TEARLINE_PG_DSN=postgresql://... uv run pytest -m live
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tearline.backends.base import RetrievalRequest, deterministic_vector
from tearline.backends.pgvector import PgVectorBackend
from tearline.domain import Chunk, Entitlement, EntitlementState, Principal
from tearline.entitlement_rule import load_rule
from tearline.fixtures import load_scenario, load_variant
from tearline.verify import check_propagation
from tests.live.harness import apply_pgvector_schema, load_pgvector

pytestmark = pytest.mark.live

DSN = os.environ.get("TEARLINE_PG_DSN")  # unprivileged: subject to the policy
ADMIN_DSN = os.environ.get("TEARLINE_PG_ADMIN_DSN")  # privileged: may bypass it
DIMENSIONS = 16
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def live() -> Iterator[tuple[PgVectorBackend, Any]]:
    """The adapter and, separately, the privileged connection the harness writes through.

    They are handed back as a pair rather than the adapter alone because the adapter has no write
    path any more (DEC-004): a test that needs to stand up an index reaches for the harness and the
    connection it writes through, which is exactly the distinction the split is there to make.
    """
    if not (DSN and ADMIN_DSN):
        pytest.skip("TEARLINE_PG_DSN and TEARLINE_PG_ADMIN_DSN are not both set")
    import psycopg

    with psycopg.connect(DSN) as connection, psycopg.connect(ADMIN_DSN) as admin:
        adapter = PgVectorBackend(connection, admin_connection=admin)
        apply_pgvector_schema(admin)
        with admin.cursor() as cursor:
            cursor.execute("GRANT SELECT ON chunks TO reader")
        admin.commit()
        yield adapter, admin


@pytest.fixture(scope="module")
def backend(live: tuple[PgVectorBackend, Any]) -> PgVectorBackend:
    return live[0]


@pytest.fixture(scope="module")
def admin(live: tuple[PgVectorBackend, Any]) -> Any:
    return live[1]


def test_the_adapter_refuses_a_role_that_bypasses_the_policy() -> None:
    """Found by the first live CI run, which reported perfect isolation from a policy that was
    never applied: a superuser bypasses row-level security, and FORCE binds the table owner rather
    than a superuser. A verification tool connected that way produces a confident right-looking
    answer by never testing the thing under test."""
    if not ADMIN_DSN:
        pytest.skip("TEARLINE_PG_ADMIN_DSN is not set")
    import psycopg

    from tearline.backends.pgvector import BypassesRowSecurity

    with psycopg.connect(ADMIN_DSN) as superuser, pytest.raises(BypassesRowSecurity):
        PgVectorBackend(superuser)


def test_the_propagation_axis_refuses_a_principals_connection() -> None:
    """Reading every chunk through a principal's connection would only ever show rows that
    principal may already see -- the one population where a mislabelled chunk cannot be found."""
    if not DSN:
        pytest.skip("TEARLINE_PG_DSN is not set")
    import psycopg

    from tearline.backends.pgvector import BypassesRowSecurity

    with psycopg.connect(DSN) as connection:
        adapter = PgVectorBackend(connection)
        with pytest.raises(BypassesRowSecurity):
            adapter.chunks()


def _load(admin: Any, variant: str) -> None:
    scenario = ROOT / "benchmarks" / "wrong-tenant-tag"
    index = load_variant(scenario, variant)
    load_pgvector(
        admin,
        [(chunk, deterministic_vector(chunk.id, DIMENSIONS)) for chunk in index.chunks.values()],
    )


def test_the_engine_enforces_the_boundary(backend: PgVectorBackend, admin: Any) -> None:
    """The property this backend is chosen for: the policy is applied by the database, so a caller
    that issues an unfiltered query still cannot read another tenant's rows."""
    _load(admin, "clean")
    acme = Principal(id="p-acme-eng", label="acme", tenant="acme", roles=frozenset({"employee"}))
    globex = Principal(
        id="p-globex-eng", label="globex", tenant="globex", roles=frozenset({"employee"})
    )

    # The query below has no WHERE clause on tenants at all -- retrieve() issues a plain
    # nearest-neighbour SELECT. Anything that comes back was permitted by the engine.
    acme_ids = backend.retrieve(RetrievalRequest(deterministic_vector("q", DIMENSIONS), acme, 20))
    globex_ids = backend.retrieve(
        RetrievalRequest(deterministic_vector("q", DIMENSIONS), globex, 20)
    )

    stored = {chunk.id: chunk for chunk in backend.chunks()}
    assert acme_ids and globex_ids
    for cid in acme_ids:
        assert "acme" in stored[cid].entitlement.tenants
    for cid in globex_ids:
        assert "globex" in stored[cid].entitlement.tenants

    # The overlap is exactly the chunks stored for BOTH tenants -- the shared handbook. An earlier
    # version asserted an empty intersection and CI caught it: a document shared across tenants is
    # the commonest legitimate pattern in any shared corpus, and `wrong-tenant-tag`'s negative set
    # explicitly forbids flagging it. The assertion had made the test demand the failure the
    # scenario forbids.
    shared = {
        cid for cid, chunk in stored.items() if {"acme", "globex"} <= chunk.entitlement.tenants
    }
    assert set(acme_ids) & set(globex_ids) == shared & set(acme_ids) & set(globex_ids)
    acme_only = {cid for cid, chunk in stored.items() if chunk.entitlement.tenants == {"acme"}}
    assert acme_only & set(globex_ids) == set(), "globex received acme-only rows"


def test_an_untagged_chunk_is_excluded_by_the_policy(backend: PgVectorBackend, admin: Any) -> None:
    """DEC-003 expressed in SQL. The policy requires a non-empty tenant array, so absence excludes
    rather than admits -- the failure `untagged-chunk`'s naive filter commits."""
    untagged = Chunk(
        id="c-untagged",
        source_document_ids=("doc-001",),
        entitlement=Entitlement(state=EntitlementState.UNKNOWN),
    )
    load_pgvector(admin, [(untagged, deterministic_vector("c-untagged", DIMENSIONS))])
    acme = Principal(id="p", label="p", tenant="acme", roles=frozenset({"employee"}))
    assert backend.retrieve(RetrievalRequest(deterministic_vector("q", DIMENSIONS), acme, 20)) == []


def test_engine_enforcement_does_not_catch_a_propagation_fault(
    backend: PgVectorBackend, admin: Any
) -> None:
    """**The argument for this tool on this backend.**

    The engine guarantees the policy is applied. It guarantees nothing about whether the stored
    tenant is the one the source document actually has. Here the faulted index is served faithfully
    and quickly to the wrong tenant, and every database-level control behaves correctly.
    """
    _load(admin, "faulted")
    scenario = ROOT / "benchmarks" / "wrong-tenant-tag"
    findings, _ = check_propagation(
        load_scenario(scenario, "wrong-tenant-tag"), load_variant(scenario, "faulted")
    )
    assert [f.chunk_id for f in findings] == ["c-0022"]

    # c-0022 belongs to a globex document and is labelled acme. The engine serves it to acme.
    acme = Principal(id="p-acme-eng", label="acme", tenant="acme", roles=frozenset({"employee"}))
    ids = backend.retrieve(RetrievalRequest(deterministic_vector("q", DIMENSIONS), acme, 20))
    assert "c-0022" in ids, "the engine enforced the stored tag, which is the point"

    stored = {chunk.id: chunk for chunk in backend.chunks()}
    rule = load_rule(scenario / "shared" / "entitlement-rule.yaml")
    assert rule.entitled(stored["c-0022"].entitlement, acme)


def test_chunks_are_read_with_the_policy_bypassed(backend: PgVectorBackend) -> None:
    """The propagation axis compares what the index HOLDS against the source system. A
    policy-filtered read would only ever show rows some principal can already see, which is exactly
    the population where a mislabelling is invisible."""
    _load(admin, "faulted")
    assert len(backend.chunks()) == 8
