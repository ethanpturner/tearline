"""Score a verification against a variant's authored expectations.

Nothing under `expected-*` reaches the verifier; it is read only here (DEC-009).

The negative sets are partly prose. `must_not_conclude` entries forbid *claims* -- "retrieval is
working correctly because nothing leaked", "the tenant boundary is broken" -- and this tool emits
no narrative, so they are vacuously satisfied rather than checked. They are counted and reported as
unchecked rather than folded into the pass, because a negative set that silently scores as passed
is the same overclaiming the project exists to prevent.

`must_not_flag` is different and is checked. Its entries name a subject -- a chunk or a probe --
that must produce no finding, which is a fact about the output rather than about a narrative. It
was counted as unchecked prose until the false-positive rate needed a denominator: a negative set
nothing reads cannot support a claim about false positives, and the evaluation plan makes one.

An `expected_unverifiable` subject in a form nothing here recognises is a **problem**, not a skip.
Six truth-set keys were authored and never read before this, and the scenarios reported `ok`
throughout -- a scorer that silently ignores what it does not understand reports the absence of a
check as a pass.
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
    #: Subjects the negative set forbids flagging, and how many were flagged anyway. The second is
    #: the false-positive count the evaluation plan reports; the first is its denominator, which is
    #: the number that stops a rate of 0/0 being written up as perfect precision.
    negative_subjects: int = 0
    false_positives: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


def _load(path: Path) -> dict[str, Any]:
    """Read one expectation file, following `inherits:` if it names another.

    A faulted variant inherits its clean variant's negative set: one planted fault must not produce
    collateral findings, and restating the clean set in each variant would let the two drift. The
    key was declared in four files and read by nothing until now, so every inherited entry was
    silently not checked -- which is the failure mode a negative set exists to catch.
    """
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    parent = raw.pop("inherits", None)
    if not parent:
        return dict(raw)
    inherited = _load((path.parent / str(parent)).resolve())
    merged = dict(inherited)
    for key, value in raw.items():
        if isinstance(value, list) and isinstance(inherited.get(key), list):
            merged[key] = [*inherited[key], *value]
        else:
            merged[key] = value
    return merged


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
            ("undetermined_returned", set(probe.undetermined_returned)),
            ("absent_from_index", set(probe.absent_from_index)),
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
    for prose_field in ("must_not_conclude", "properties_absent"):
        result.unchecked_prose += len(clean.get(prose_field) or [])
    _score_negative_set(result, clean, findings, report)

    unver = _load(expected_dir / "expected-unverifiable.yaml")
    for row in unver.get("expected_unverifiable") or []:
        subject = str(row.get("subject", ""))
        result.checked += 1
        if subject.startswith("chunk "):
            chunk_id = subject.split(" ", 1)[1]
            finding = findings.get(chunk_id)
            if finding is None or finding.verdict.value != "unverifiable":
                got = finding.verdict.value if finding else "no finding"
                result.problems.append(f"{chunk_id} expected unverifiable, got {got}")
        elif subject.startswith("probe "):
            if subject.split(" ", 1)[1] not in report.probes_skipped:
                result.problems.append(f"{subject} expected skipped and was not")
        elif subject.startswith("cause of the ") and subject.endswith(" mismatch"):
            # The mismatch is established; only its cause is not. DEC-016 keeps those on separate
            # axes precisely so this row can assert one while the finding asserts the other.
            chunk_id = subject.removeprefix("cause of the ").removesuffix(" mismatch")
            finding = findings.get(chunk_id)
            if finding is None:
                result.problems.append(f"{subject}: no finding on {chunk_id}")
            elif finding.cause.value != "undetermined":
                result.problems.append(
                    f"{subject}: cause {finding.cause.value}, expected undetermined"
                )
        else:
            # Not a skip. An unrecognised subject means the truth set asserts something the scorer
            # does not check, and reporting that as a pass is the overclaiming this project exists
            # to prevent -- exactly what six unread keys were doing here before.
            result.problems.append(
                f"expected_unverifiable subject {subject!r} is in no form the scorer recognises, "
                "so this expectation was not checked"
            )
    return result


def _score_negative_set(
    result: Score,
    clean: dict[str, Any],
    findings: dict[str, Any],
    report: VerificationReport,
) -> None:
    """Check `must_not_flag`. Every entry names a chunk or a probe that must produce no finding.

    A flagged one is a **false positive** rather than an ordinary failure. The distinction matters
    for the evaluation plan: precision is a claim about how often the tool reports a fault that is
    not there, and it can only be measured against subjects authored as definitely-not-faults.
    """
    flagged_probes = {p.probe_id for p in report.probes if p.verdict.value == "contradicted"}
    for row in clean.get("must_not_flag") or []:
        case = str(row.get("case", ""))
        subject = case.split(" ", 1)[0]
        if " is not flagged" not in case:
            result.unchecked_prose += 1
            continue
        result.checked += 1
        result.negative_subjects += 1
        if subject in findings or subject in flagged_probes:
            result.false_positives.append(subject)
            result.problems.append(f"false positive: {subject} is in the negative set and flagged")
