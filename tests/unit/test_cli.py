"""The command surface: what the exit status says, and what the JSON form carries.

A caller in CI reads the exit status and nothing else. It has to mean what the report means.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from tearline import ROOT, _cmd_verify, exit_status
from tearline.domain import (
    ProbeOutcome,
    ProbeResult,
    Verdict,
    VerificationReport,
)


def _report(**overrides: object) -> VerificationReport:
    base: dict[str, object] = {
        "chunks_examined": 4,
        "chunks_untraceable": 0,
        "propagation": (),
        "probes": (),
        "probes_skipped": (),
        "partial": False,
    }
    return VerificationReport(**{**base, **overrides})  # type: ignore[arg-type]


def _probe(verdict: Verdict, outcome: ProbeOutcome, under: frozenset[str]) -> ProbeResult:
    return ProbeResult(
        probe_id="pr-001",
        principal_id="p-globex-eng",
        returned=(),
        over_retrieved=frozenset(),
        under_retrieved=under,
        verdict=verdict,
        outcome=outcome,
    )


def test_a_contradicted_probe_alone_makes_the_exit_status_non_zero() -> None:
    """DEC-024. Before it, `post-filter-truncation/truncating` -- every tag correct, one tenant
    served nothing -- exited 0, and so did an over-retrieval on a correctly tagged index. The
    exit status told a caller the boundary held in exactly the two cases DEC-008 and DEC-018 say
    it did not."""
    clean = _probe(Verdict.VERIFIED, ProbeOutcome.CLEAN, frozenset())
    under = _probe(Verdict.CONTRADICTED, ProbeOutcome.UNDER_RETRIEVAL, frozenset({"c-0101"}))
    assert exit_status(_report(probes=(clean,))) == 0
    assert exit_status(_report(probes=(clean, under))) == 1
    assert exit_status(_report(partial=True)) == 1


def test_the_truncating_variant_exits_non_zero_from_the_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The scenario named in the decision, run through the command rather than the function."""
    args = argparse.Namespace(
        scenario=str(ROOT / "benchmarks" / "post-filter-truncation"),
        variant="truncating",
        json=False,
    )
    assert _cmd_verify(args) == 1
    assert "under-retrieval" in capsys.readouterr().out


def test_the_json_form_is_the_domain_object_and_nothing_else(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--json` serialises `VerificationReport` and adds no field on the way out, so DEC-002 holds
    for it by construction: the model has nowhere to put chunk content. Checked structurally --
    the keys are the model's declared fields and no nested key names content -- and against the
    fixture: no document label from the scenario appears anywhere in the output."""
    path = ROOT / "benchmarks" / "post-filter-truncation"
    args = argparse.Namespace(scenario=str(path), variant="truncating", json=True)
    assert _cmd_verify(args) == 1
    out = capsys.readouterr().out
    report = json.loads(out)
    assert set(report) == set(VerificationReport.model_fields)
    forbidden = {"text", "content", "body", "excerpt", "snippet"}
    assert not forbidden & _keys(report)
    for label in _labels(path / "shared" / "documents.yaml"):
        assert label not in out, f"document label {label!r} reached the JSON report"
    assert any(p["outcome"] == "under-retrieval" for p in report["probes"])


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _labels(documents: Path) -> list[str]:
    import yaml

    raw = yaml.safe_load(documents.read_text()) or {}
    docs = raw.get("documents") or raw
    items = docs.values() if isinstance(docs, dict) else docs
    return [str(d["label"]) for d in items if isinstance(d, dict) and d.get("label")]
