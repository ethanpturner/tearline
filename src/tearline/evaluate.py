"""Score a verification against a variant's authored expectations.

Nothing under `expected-*` reaches the verifier; it is read only here (DEC-009).

The negative sets are partly prose. `must_not_conclude` entries forbid *claims* -- "retrieval is
working correctly because nothing leaked", "the tenant boundary is broken" -- and this tool emits
no narrative, so they are vacuously satisfied rather than checked. They are counted and reported as
unchecked rather than folded into the pass, because a negative set that silently scores as passed
is the same overclaiming the project exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tearline.domain import VerificationReport


@dataclass
class Score:
    scenario: str
    variant: str
    problems: list[str] = field(default_factory=list)
    checked: int = 0
    unchecked_prose: int = 0

    @property
    def passed(self) -> bool:
        return not self.problems


def _load(path: Path) -> dict[str, Any]:
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def score(report: VerificationReport, expected_dir: Path, scenario: str, variant: str) -> Score:
    result = Score(scenario=scenario, variant=variant)
    findings = {f.chunk_id: f for f in report.propagation}

    prop = _load(expected_dir / "expected-propagation.yaml")
    for row in prop.get("expected_findings") or []:
        result.checked += 1
        finding = findings.get(str(row["chunk_id"]))
        if finding is None:
            result.problems.append(f"missed propagation finding on {row['chunk_id']}")
            continue
        if row.get("verdict") and finding.verdict.value != row["verdict"]:
            result.problems.append(
                f"{row['chunk_id']} verdict {finding.verdict.value} != {row['verdict']}"
            )
        if row.get("cause") and finding.cause.value != row["cause"]:
            result.problems.append(
                f"{row['chunk_id']} cause {finding.cause.value} != {row['cause']}"
            )
    expected_ids = {str(r["chunk_id"]) for r in (prop.get("expected_findings") or [])}
    for extra in set(findings) - expected_ids:
        result.problems.append(f"unexpected propagation finding on {extra}")
    for count_field in ("chunks_examined", "chunks_untraceable"):
        if count_field in prop:
            result.checked += 1
            actual_count = getattr(report, count_field)
            if actual_count != prop[count_field]:
                result.problems.append(f"{count_field} {actual_count} != {prop[count_field]}")
    for row in prop.get("forbidden_verdicts") or []:
        result.checked += 1
        finding = findings.get(str(row["chunk_id"]))
        if finding is not None and finding.verdict.value == row["verdict"]:
            result.problems.append(f"forbidden verdict {row['verdict']} on {row['chunk_id']}")
    for row in prop.get("forbidden_causes") or []:
        result.checked += 1
        finding = findings.get(str(row["chunk_id"]))
        if finding is not None and finding.cause.value == row["cause"]:
            result.problems.append(f"forbidden cause {row['cause']} on {row['chunk_id']}")

    vis = _load(expected_dir / "expected-visibility.yaml")
    by_key = {(p.probe_id, p.principal_id): p for p in report.probes}
    for row in vis.get("visibility") or []:
        result.checked += 1
        key = (str(row["probe"]), str(row["principal"]))
        probe = by_key.get(key)
        if probe is None:
            result.problems.append(f"{key} expected but not produced")
            continue
        for label, actual in (
            ("visible", set(probe.returned)),
            ("over_retrieved", set(probe.over_retrieved)),
            ("under_retrieved", set(probe.under_retrieved)),
        ):
            if label in row and set(row[label] or []) != actual:
                result.problems.append(
                    f"{key} {label} {sorted(actual)} != {sorted(row[label] or [])}"
                )
        if row.get("outcome") and probe.outcome.value != row["outcome"]:
            result.problems.append(f"{key} outcome {probe.outcome.value} != {row['outcome']}")
    for key in set(by_key) - {
        (str(r["probe"]), str(r["principal"])) for r in (vis.get("visibility") or [])
    }:
        result.problems.append(f"{key} produced but not expected")
    if "probes_skipped" in vis:
        result.checked += 1
        if set(vis["probes_skipped"] or []) != set(report.probes_skipped):
            result.problems.append(
                f"probes_skipped {sorted(report.probes_skipped)} != {sorted(vis['probes_skipped'] or [])}"
            )

    clean = _load(expected_dir / "expected-clean.yaml")
    for prose_field in ("must_not_flag", "must_not_conclude", "properties_absent"):
        result.unchecked_prose += len(clean.get(prose_field) or [])
    unver = _load(expected_dir / "expected-unverifiable.yaml")
    for row in unver.get("expected_unverifiable") or []:
        subject = str(row.get("subject", ""))
        if subject.startswith("chunk "):
            result.checked += 1
            chunk_id = subject.split(" ", 1)[1]
            finding = findings.get(chunk_id)
            if finding is None or finding.verdict.value != "unverifiable":
                result.problems.append(
                    f"{chunk_id} expected unverifiable, got {finding.verdict.value if finding else 'no finding'}"
                )
        elif subject.startswith("probe "):
            result.checked += 1
            if subject.split(" ", 1)[1] not in report.probes_skipped:
                result.problems.append(f"{subject} expected skipped and was not")
    return result
