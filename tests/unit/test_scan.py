"""The live path, end to end, without a live store.

`scan` is the only code path that reads an ACL from a real system and asks a real index what it
returned. That makes it the path most worth testing and the hardest to test, since both ends are
external. Here the source end is real -- a temporary directory with real POSIX modes -- and the
store end is a fake that answers exactly as instructed, so the test can state what the store said
and check what the tool concluded from it.

What this does not do is verify either adapter. That needs the store, and `tests/live/` is where it
happens. What it does verify is everything between: that the tool prefers what the store returned
over what a fixture asserts, that truth still comes from the source system rather than from the
index, and that a store returning a chunk nobody is entitled to is reported.
"""

from __future__ import annotations

import grp
import os
from pathlib import Path

import pytest

from tearline.backends.base import RetrievalRequest
from tearline.domain import Chunk, Entitlement, EntitlementState, ProbeOutcome, Verdict
from tearline.scan import ScanError, Target, load_target, scan
from tearline.sources import FilesystemSource

RULE = """
system: fixture
rule:
  tenant: member
  role: intersects-or-everyone
  direct: principal-listed
  combine: tenant AND (role OR direct)
"""
PRINCIPALS = """
principals:
  - {id: p-acme, label: acme, tenant: acme, roles: [everyone]}
  - {id: p-globex, label: globex, tenant: globex, roles: [everyone]}
"""
PROBES = """
probes:
  - {id: pr-001, query: quarterly plans, principals: [p-acme, p-globex],
     matches: [c-acme, c-globex]}
"""


class FakeBackend:
    """A store that returns exactly what it was told to, and records what it was asked."""

    enforcement_site = "application"

    def __init__(self, stored: list[Chunk], answers: dict[str, list[str]]) -> None:
        self._stored = stored
        self._answers = answers
        self.requests: list[RetrievalRequest] = []

    def chunks(self) -> list[Chunk]:
        return list(self._stored)

    def retrieve(self, request: RetrievalRequest) -> list[str]:
        self.requests.append(request)
        return list(self._answers.get(request.principal.id, []))


@pytest.fixture
def target_dir(tmp_path: Path) -> Path:
    """A source system with two real files, group-owned and mode-set for real."""
    group = grp.getgrgid(os.getgid()).gr_name
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "acme.txt").write_text("acme material")
    os.chmod(corpus / "acme.txt", 0o644)
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "entitlement-rule.yaml").write_text(RULE)
    (shared / "principals.yaml").write_text(PRINCIPALS)
    (shared / "probes.yaml").write_text(PROBES)
    (tmp_path / "target.yaml").write_text(
        f"source:\n  kind: filesystem\n  root: corpus\n  group_to_tenant:\n    {group}: acme\n"
        f"backend:\n  kind: qdrant\n  base_url: http://localhost:6333\n"
    )
    return tmp_path


def _target(path: Path, backend: FakeBackend) -> Target:
    source = FilesystemSource(
        root=path / "corpus",
        group_to_tenant={grp.getgrgid(os.getgid()).gr_name: "acme"},
    )
    return Target(source=source, backend=backend, enforcement="rule", ann_limit=None)


def _chunk(cid: str, doc: str, tenants: set[str]) -> Chunk:
    return Chunk(
        id=cid,
        source_document_ids=(doc,),
        entitlement=Entitlement(
            state=EntitlementState.STATED,
            tenants=frozenset(tenants),
            roles=frozenset({"everyone"}),
        ),
    )


def test_the_scan_reports_what_the_store_returned_not_what_the_index_implies(
    target_dir: Path,
) -> None:
    """The whole reason the live path exists.

    Both chunks carry a correct tenant tag, so anything reasoning from the index alone concludes the
    boundary holds. The store hands globex an acme chunk anyway -- the application forgot its filter
    on this query path, which is DEC-018's failure mode exactly -- and only asking it reveals that.
    """
    stored = [
        _chunk("c-acme", "acme.txt", {"acme"}),
        _chunk("c-globex", "elsewhere.txt", {"globex"}),
    ]
    backend = FakeBackend(stored, {"p-acme": ["c-acme"], "p-globex": ["c-globex", "c-acme"]})
    report = scan(target_dir, _target(target_dir, backend))

    assert report.enforcement_site == "application"
    leak = next(p for p in report.probes if p.principal_id == "p-globex")
    assert leak.verdict is Verdict.CONTRADICTED
    assert leak.outcome is ProbeOutcome.OVER_RETRIEVAL
    assert leak.over_retrieved == frozenset({"c-acme"})
    # `c-globex` is backed by a document not on this filesystem, so its entitlement is
    # undetermined. It was returned, and that is reported without being called a disclosure.
    assert leak.undetermined_returned == frozenset({"c-globex"})
    assert next(p for p in report.probes if p.principal_id == "p-acme").verdict is Verdict.VERIFIED


def test_truth_comes_from_the_source_system_and_not_from_the_index(target_dir: Path) -> None:
    """A store agreeing with its own wrong tag is still wrong.

    `c-acme` is tagged for globex in the index, and the store faithfully serves it to globex. Every
    component agrees with every other; the only thing that disagrees is the file on disk, which is
    ground truth (DEC-005). Anything grading the store against the index passes this.
    """
    stored = [_chunk("c-acme", "acme.txt", {"globex"})]
    backend = FakeBackend(stored, {"p-acme": [], "p-globex": ["c-acme"]})
    report = scan(target_dir, _target(target_dir, backend))

    assert [(f.chunk_id, f.verdict) for f in report.propagation] == [
        ("c-acme", Verdict.CONTRADICTED)
    ]
    globex = next(p for p in report.probes if p.principal_id == "p-globex")
    assert globex.over_retrieved == frozenset({"c-acme"})
    acme = next(p for p in report.probes if p.principal_id == "p-acme")
    assert acme.under_retrieved == frozenset({"c-acme"}), "acme owns the file and got nothing"


def test_a_chunk_the_store_returned_that_the_inventory_does_not_hold_is_undetermined(
    target_dir: Path,
) -> None:
    """An id the inventory read never saw -- a stale point, a second collection, a race with
    ingestion. It is reported rather than ignored, and it is **not** counted as a disclosure:
    nothing establishes the principal was entitled and nothing establishes they were not.

    Calling it a leak would be the tool doing what it exists to stop others doing -- reporting an
    absence of evidence as evidence of a breach.
    """
    backend = FakeBackend(
        [_chunk("c-acme", "acme.txt", {"acme"})],
        {"p-acme": ["c-acme"], "p-globex": ["c-ghost"]},
    )
    report = scan(target_dir, _target(target_dir, backend))
    globex = next(p for p in report.probes if p.principal_id == "p-globex")
    assert globex.undetermined_returned == frozenset({"c-ghost"})
    assert "c-ghost" not in globex.over_retrieved


def test_an_unlisted_but_entitled_chunk_is_not_a_finding(target_dir: Path) -> None:
    """Relevance is not under test (DEC-011). A store returning something the probe never listed is
    making a claim about relevance, and this tool does not grade that -- only whether the principal
    was entitled to what came back."""
    stored = [
        _chunk("c-acme", "acme.txt", {"acme"}),
        _chunk("c-extra", "acme.txt", {"acme"}),
    ]
    backend = FakeBackend(stored, {"p-acme": ["c-acme", "c-extra"], "p-globex": []})
    report = scan(target_dir, _target(target_dir, backend))
    acme = next(p for p in report.probes if p.principal_id == "p-acme")
    assert acme.verdict is Verdict.VERIFIED
    assert "c-extra" not in acme.over_retrieved


def test_the_store_is_asked_for_the_whole_index_when_no_limit_is_declared(
    target_dir: Path,
) -> None:
    """A limit the tool chose would let its own truncation register as the store's under-retrieval,
    which is a finding about the wrong system (DEC-019)."""
    stored = [_chunk(f"c-{i}", "acme.txt", {"acme"}) for i in range(5)]
    backend = FakeBackend(stored, {})
    scan(target_dir, _target(target_dir, backend))
    assert {r.limit for r in backend.requests} == {5}


def test_a_source_without_a_group_mapping_is_refused(target_dir: Path) -> None:
    """DEC-020: guessing the mapping would surface as confident findings about the index."""
    (target_dir / "target.yaml").write_text(
        "source:\n  kind: filesystem\n  root: corpus\n"
        "backend:\n  kind: qdrant\n  base_url: http://localhost:6333\n"
    )
    with pytest.raises(ScanError, match="group_to_tenant"):
        load_target(target_dir)


def test_an_unknown_backend_is_refused(target_dir: Path) -> None:
    (target_dir / "target.yaml").write_text(
        "source:\n  kind: filesystem\n  root: corpus\n  group_to_tenant: {x: y}\n"
        "backend:\n  kind: pinecone\n"
    )
    with pytest.raises(ScanError, match="pinecone"):
        load_target(target_dir)
