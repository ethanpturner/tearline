"""The pgvector + RLS backend, against a real PostgreSQL.

Deselected by default (`-m "not live"` in addopts). CI runs them against a `pgvector/pgvector`
service container; there is no local Postgres, so this is where the adapter is actually verified.

Run with: TEARLINE_PG_DSN=postgresql://... uv run pytest -m live
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tearline.backends.base import RetrievalRequest, deterministic_vector
from tearline.backends.pgvector import PgVectorBackend
from tearline.domain import Chunk, Entitlement, EntitlementState, Principal
from tearline.fixtures import load_scenario, load_variant
from tearline.rules import entitled_by_rule
from tearline.verify import check_propagation

pytestmark = pytest.mark.live

DSN = os.environ.get("TEARLINE_PG_DSN")
DIMENSIONS = 16
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def backend() -> Iterator[PgVectorBackend]:
    if not DSN:
        pytest.skip("TEARLINE_PG_DSN is not set")
    import psycopg

    with psycopg.connect(DSN) as connection:
        adapter = PgVectorBackend(connection)
        adapter.apply_schema()
        yield adapter


def _load(adapter: PgVectorBackend, variant: str) -> None:
    scenario = ROOT / "benchmarks" / "wrong-tenant-tag"
    index = load_variant(scenario, variant)
    adapter.load(
        [(chunk, deterministic_vector(chunk.id, DIMENSIONS)) for chunk in index.chunks.values()]
    )


def test_the_engine_enforces_the_boundary(backend: PgVectorBackend) -> None:
    """The property this backend is chosen for: the policy is applied by the database, so a caller
    that issues an unfiltered query still cannot read another tenant's rows."""
    _load(backend, "clean")
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
    assert set(acme_ids) & set(globex_ids) == set()


def test_an_untagged_chunk_is_excluded_by_the_policy(backend: PgVectorBackend) -> None:
    """DEC-003 expressed in SQL. The policy requires a non-empty tenant array, so absence excludes
    rather than admits -- the failure `untagged-chunk`'s naive filter commits."""
    untagged = Chunk(
        id="c-untagged",
        source_document_ids=("doc-001",),
        entitlement=Entitlement(state=EntitlementState.UNKNOWN),
    )
    backend.load([(untagged, deterministic_vector("c-untagged", DIMENSIONS))])
    acme = Principal(id="p", label="p", tenant="acme", roles=frozenset({"employee"}))
    assert backend.retrieve(RetrievalRequest(deterministic_vector("q", DIMENSIONS), acme, 20)) == []


def test_engine_enforcement_does_not_catch_a_propagation_fault(backend: PgVectorBackend) -> None:
    """**The argument for this tool on this backend.**

    The engine guarantees the policy is applied. It guarantees nothing about whether the stored
    tenant is the one the source document actually has. Here the faulted index is served faithfully
    and quickly to the wrong tenant, and every database-level control behaves correctly.
    """
    _load(backend, "faulted")
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
    assert entitled_by_rule(stored["c-0022"].entitlement, acme)


def test_chunks_are_read_with_the_policy_bypassed(backend: PgVectorBackend) -> None:
    """The propagation axis compares what the index HOLDS against the source system. A
    policy-filtered read would only ever show rows some principal can already see, which is exactly
    the population where a mislabelling is invisible."""
    _load(backend, "faulted")
    assert len(backend.chunks()) == 8
