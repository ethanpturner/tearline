"""Every registered variant, scored against its authored expectations."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tearline.evaluate import score
from tearline.fixtures import load_scenario, load_variant, variants_of
from tearline.verify import verify

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = yaml.safe_load((ROOT / "benchmarks" / "scenarios.yaml").read_text())
CASES = [
    (e["slug"], e["path"], v)
    for e in REGISTRY["scenarios"]
    if e["status"] == "recorded"
    for v in variants_of(ROOT / str(e["path"]))
]


@pytest.mark.parametrize(("slug", "path", "variant"), CASES, ids=[f"{s}/{v}" for s, _, v in CASES])
def test_variant(slug: str, path: str, variant: str) -> None:
    scenario_path = ROOT / path
    report = verify(load_scenario(scenario_path, slug), load_variant(scenario_path, variant))
    result = score(report, scenario_path / variant, slug, variant)
    assert result.passed, result.problems


def test_a_clean_variant_never_produces_a_fault() -> None:
    """A scenario without its clean twin measures recall and says nothing about false positives.

    Note what "clean" does and does not mean. It forbids a *fault* -- a `contradicted` finding, or
    any retrieval delta. It does not forbid a *finding*: boundary-crossing-chunk/clean correctly
    reports c-0051 as `unverifiable`, because a chunk whose entitlement cannot be verified is
    reported with its reason rather than silently counted as fine. An earlier version of this test
    conflated the two and failed on exactly that case.
    """
    for slug, path, variant in CASES:
        if variant != "clean":
            continue
        scenario_path = ROOT / path
        report = verify(load_scenario(scenario_path, slug), load_variant(scenario_path, variant))
        faults = [f for f in report.propagation if f.verdict.value == "contradicted"]
        assert not faults, f"{slug}/clean produced faults: {[f.chunk_id for f in faults]}"
        assert all(p.outcome.value == "clean" for p in report.probes), slug


def test_a_skipped_probe_never_contributes_a_result() -> None:
    """ "No leak detected" from a one-identity probe is the forbidden output (DEC-007)."""
    path = ROOT / "benchmarks" / "single-principal-probe"
    report = verify(load_scenario(path, "single-principal-probe"), load_variant(path, "clean"))
    assert "pr-009" in report.probes_skipped
    assert not [p for p in report.probes if p.probe_id == "pr-009"]
    assert report.partial


def test_the_negative_set_is_derived_and_not_merely_authored() -> None:
    """DEC-023. Precision is measured over every subject the truth set does not name as a fault.

    The figure was "0 of 3" when only entries phrased as "X is not flagged" counted, which measured
    how much prose somebody had typed rather than how many chances the tool had to invent a
    finding. A scenario with one planted fault and seven correct chunks offers seven.
    """
    total = 0
    for entry in yaml.safe_load((ROOT / "benchmarks" / "scenarios.yaml").read_text())["scenarios"]:
        if entry["status"] != "recorded":
            continue
        path = ROOT / str(entry["path"])
        scenario = load_scenario(path, str(entry["slug"]))
        for variant in variants_of(path):
            result = score(
                verify(scenario, load_variant(path, variant)),
                path / variant,
                str(entry["slug"]),
                variant,
            )
            assert not result.false_positives, result.false_positives
            total += result.negative_subjects
    # Not pinned exactly -- adding a scenario should raise it without editing this test -- but a
    # collapse back toward the handful of authored subjects is what this guards against.
    assert total >= 60, f"the negative set shrank to {total} subjects"
