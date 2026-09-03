"""The filesystem source adapter, and the drift signal it makes observable."""

from __future__ import annotations

import grp
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from tearline.domain import Chunk, EntitlementState, MismatchCause, Verdict
from tearline.entitlement_rule import EntitlementRule
from tearline.fixtures import Scenario, Variant
from tearline.sources import FilesystemSource
from tearline.verify import check_propagation

FIXTURE_RULE = EntitlementRule(
    system="posix-filesystem",
    tenant="member",
    role="intersects-or-everyone",
    direct="principal-listed",
    combine="tenant AND (role OR direct)",
)


def _source(root: Path) -> FilesystemSource:
    (root / "shared.txt").write_text("public")
    (root / "internal.txt").write_text("restricted")
    os.chmod(root / "shared.txt", 0o644)
    os.chmod(root / "internal.txt", 0o640)
    group = grp.getgrgid((root / "shared.txt").stat().st_gid).gr_name
    return FilesystemSource(root, {group: "acme"})


def test_world_readable_is_a_stated_role_not_an_absence(tmp_path: Path) -> None:
    """DEC-003. `everyone` is a grant the source system makes, not a missing restriction, so it is
    recorded as a stated role rather than as an empty entitlement."""
    docs = _source(tmp_path).documents()
    assert docs["shared.txt"].entitlement.roles == {"everyone"}
    assert docs["internal.txt"].entitlement.roles == {"member"}
    assert docs["shared.txt"].entitlement.state is EntitlementState.STATED


def test_an_unmapped_group_is_unknown_not_a_grant(tmp_path: Path) -> None:
    """A group the mapping does not cover yields `unknown`, never an empty-but-stated entitlement
    that a naive filter would read as unrestricted."""
    (tmp_path / "x.txt").write_text("x")
    docs = FilesystemSource(tmp_path, {}).documents()
    assert docs["x.txt"].entitlement.state is EntitlementState.UNKNOWN
    assert docs["x.txt"].entitlement.tenants == frozenset()


def test_a_chmod_after_ingestion_reads_as_drift(tmp_path: Path) -> None:
    """The point of a real source system: `chmod` moves st_ctime, so the mismatch it creates is
    attributable rather than `undetermined` (DEC-006).

    Without a timestamp the tool can only say the index and the source disagree. With one it can
    say the index was right and went stale, which sends an operator to re-index rather than to
    audit a pipeline that is working.
    """
    source = _source(tmp_path)
    ingested = datetime.now(tz=UTC)
    stored = source.documents()["shared.txt"]

    time.sleep(1.1)
    os.chmod(tmp_path / "shared.txt", 0o640)  # world-readable no longer

    scenario = Scenario(
        slug="drift",
        documents=source.documents(),
        principals={},
        probes=(),
        rule=FIXTURE_RULE,
    )
    variant = Variant(
        name="stale",
        chunks={
            "c-1": Chunk(
                id="c-1",
                source_document_ids=("shared.txt",),
                ingested_at=ingested,
                # The entitlement as it was at ingestion: still carrying `everyone`.
                entitlement=stored.entitlement,
            )
        },
        enforcement="rule",
        ann_limit=None,
    )
    findings, _ = check_propagation(scenario, variant)
    assert [f.chunk_id for f in findings] == ["c-1"]
    assert findings[0].verdict is Verdict.CONTRADICTED
    assert findings[0].cause is MismatchCause.DRIFT
