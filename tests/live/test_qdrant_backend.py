"""The Qdrant backend, against a real Qdrant.

Deselected by default. CI runs these against a `qdrant/qdrant` service container.

Run with: TEARLINE_QDRANT_URL=http://localhost:6333 uv run pytest -m live
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tearline.backends.base import RetrievalRequest, deterministic_vector
from tearline.backends.qdrant import COLLECTION, DIMENSIONS, QdrantBackend
from tearline.domain import Principal
from tearline.fixtures import load_scenario, load_variant
from tearline.verify import check_propagation
from tests.live.harness import apply_qdrant_schema, load_qdrant

pytestmark = pytest.mark.live

URL = os.environ.get("TEARLINE_QDRANT_URL")
ROOT = Path(__file__).resolve().parents[2]
ACME = Principal(id="p-acme-eng", label="acme", tenant="acme", roles=frozenset({"employee"}))
GLOBEX = Principal(
    id="p-globex-eng", label="globex", tenant="globex", roles=frozenset({"employee"})
)


@pytest.fixture(scope="module")
def backend() -> Iterator[QdrantBackend]:
    if not URL:
        pytest.skip("TEARLINE_QDRANT_URL is not set")
    adapter = QdrantBackend(URL)
    apply_qdrant_schema(adapter, COLLECTION)
    yield adapter


def _load(adapter: QdrantBackend, variant: str) -> None:
    index = load_variant(ROOT / "benchmarks" / "wrong-tenant-tag", variant)
    load_qdrant(
        adapter,
        COLLECTION,
        [(chunk, deterministic_vector(chunk.id, DIMENSIONS)) for chunk in index.chunks.values()],
    )


def test_the_application_filter_holds_the_boundary(backend: QdrantBackend) -> None:
    _load(backend, "clean")
    stored = {chunk.id: chunk for chunk in backend.chunks()}
    query = RetrievalRequest(deterministic_vector("q", DIMENSIONS), GLOBEX, 20)
    for cid in backend.retrieve(query):
        assert "globex" in stored[cid].entitlement.tenants


def test_the_store_does_not_enforce_the_boundary(backend: QdrantBackend) -> None:
    """**The contrast with DEC-017, demonstrated rather than asserted.**

    The same query with the filter omitted returns another tenant's points, correctly and quickly.
    No configuration of the store prevents it, because the boundary lives entirely in the
    application code that writes the filter. On the engine-enforced backend the equivalent query
    returns nothing a principal may not see.

    This is not a defect in Qdrant. It is where the boundary is, and a tool that verified only
    engine-enforced stores would have nothing to say about the far more common shape.
    """
    _load(backend, "clean")
    stored = {chunk.id: chunk for chunk in backend.chunks()}
    query = RetrievalRequest(deterministic_vector("q", DIMENSIONS), GLOBEX, 20)

    filtered = set(backend.retrieve(query))
    unfiltered = set(backend.retrieve_unfiltered(query))

    leaked = {cid for cid in unfiltered if "globex" not in stored[cid].entitlement.tenants}
    assert leaked, "omitting the filter returned nothing a globex principal may not see"
    assert leaked & filtered == set(), "the filtered query already leaked"


def test_an_untagged_chunk_is_excluded_by_the_filter(backend: QdrantBackend) -> None:
    """The filter matches a tenant value, so a point with an empty tenant list matches nothing.

    Note what this does and does not show. It is correct *because the filter is written as a
    positive match*. A filter written as an exclusion -- everything whose tenant differs -- would
    admit it, which is `untagged-chunk`'s naive variant, and nothing in the store would object.
    """
    _load(backend, "clean")
    from tearline.domain import Chunk, Entitlement, EntitlementState

    untagged = Chunk(
        id="c-untagged",
        source_document_ids=("doc-001",),
        entitlement=Entitlement(state=EntitlementState.UNKNOWN),
    )
    load_qdrant(backend, COLLECTION, [(untagged, deterministic_vector("c-untagged", DIMENSIONS))])
    query = RetrievalRequest(deterministic_vector("c-untagged", DIMENSIONS), ACME, 20)
    assert "c-untagged" not in backend.retrieve(query)
    assert "c-untagged" in backend.retrieve_unfiltered(query)


def test_application_enforcement_does_not_catch_a_propagation_fault(backend: QdrantBackend) -> None:
    """Same argument as the engine-enforced backend, reached from the other direction: the filter
    is applied faithfully to a tag that is wrong."""
    _load(backend, "faulted")
    scenario = ROOT / "benchmarks" / "wrong-tenant-tag"
    findings, _ = check_propagation(
        load_scenario(scenario, "wrong-tenant-tag"), load_variant(scenario, "faulted")
    )
    assert [f.chunk_id for f in findings] == ["c-0022"]
    ids = backend.retrieve(RetrievalRequest(deterministic_vector("q", DIMENSIONS), ACME, 20))
    assert "c-0022" in ids, "the filter enforced the stored tag, which is the point"
