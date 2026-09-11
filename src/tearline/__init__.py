"""tearline — retrieval entitlement verification."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tearline.domain import Verdict, VerificationReport
from tearline.evaluate import score
from tearline.fixtures import load_scenario, load_variant, variants_of
from tearline.scan import load_target, scan
from tearline.verify import verify

ROOT = Path(__file__).resolve().parent.parent.parent


#: What each enforcement site means for a clean result. Printed with every report because the same
#: verdict carries different weight on each (DEC-010, DEC-017, DEC-018), and a reader comparing two
#: runs without knowing which is which will draw the wrong conclusion from identical output.
SITE_MEANING = {
    "engine": (
        "the database evaluated the policy, so retrieval code that omits its filter still cannot "
        "read another tenant's rows. What that does not establish is whether the policy expresses "
        "the source system's ACL, which is what the propagation findings above address."
    ),
    "application": (
        "the boundary was applied by retrieval code, not by the store. A clean result says this "
        "query path filtered correctly; it says nothing about any other query path against the "
        "same collection, and the store does not require one."
    ),
    "simulated": (
        "probes were computed from the fixture's authored expectations. No store was asked, so "
        "nothing here establishes that a real index applies the boundary."
    ),
}


def _print_report(report: VerificationReport, title: str) -> None:
    print(
        f"{title}: {report.chunks_examined} chunks, "
        f"{report.chunks_untraceable} untraceable, partial={report.partial}"
    )
    print(
        f"  enforcement site: {report.enforcement_site} -- {SITE_MEANING[report.enforcement_site]}"
    )
    for finding in report.propagation:
        print(f"  {finding.verdict.value:13} {finding.chunk_id}  cause={finding.cause.value}")
        if finding.detail:
            print(f"      {finding.detail}")
    for probe in report.probes:
        if probe.outcome.value == "clean":
            continue
        print(
            f"  {probe.outcome.value:15} {probe.probe_id}/{probe.principal_id} "
            f"over={sorted(probe.over_retrieved)} under={sorted(probe.under_retrieved)}"
        )
    for probe in report.probes:
        if probe.undetermined_returned:
            print(
                f"  undetermined    {probe.probe_id}/{probe.principal_id} "
                f"{sorted(probe.undetermined_returned)}: returned, and no source document "
                f"establishes whether that was permitted. Not counted as a disclosure"
            )
        if probe.absent_from_index:
            print(
                f"  not-in-index    {probe.probe_id}/{probe.principal_id} "
                f"{sorted(probe.absent_from_index)}: the probe names chunks the index does not "
                f"hold, so it exercised less of the boundary than it describes"
            )
    for skipped in report.probes_skipped:
        print(
            f"  not-run         {skipped}: fewer than two identities; nothing about the boundary "
            f"was exercised"
        )


def exit_status(report: VerificationReport) -> int:
    """Non-zero when the report carries anything a caller must not ignore (DEC-024).

    Three things qualify: a propagation finding, a probe whose verdict is `contradicted` on either
    axis, and a partial run. Before DEC-024 only the first and last did, so a correctly tagged index
    that served one tenant another's chunk -- or served an entitled tenant nothing -- exited 0, and a
    caller reading the exit status alone was told the boundary held.
    """
    contradicted = any(probe.verdict is Verdict.CONTRADICTED for probe in report.probes)
    return 1 if (report.propagation or contradicted or report.partial) else 0


def _emit(report: VerificationReport, title: str, as_json: bool) -> None:
    """The report as text, or as the domain object serialised.

    The JSON form is `VerificationReport.model_dump_json()` and nothing else: no field is added on
    the way out, so DEC-002 holds for it by construction -- the model has no field that can hold
    chunk content, and the serialiser has nowhere to put any.
    """
    if as_json:
        print(report.model_dump_json(indent=2))
    else:
        _print_report(report, title)


def _cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.scenario)
    report = verify(load_scenario(path, path.name), load_variant(path, args.variant))
    _emit(report, f"{path.name}/{args.variant}", args.json)
    return exit_status(report)


def _cmd_scan(args: argparse.Namespace) -> int:
    """Run against a real source system and a real index. Reads only (DEC-004)."""
    path = Path(args.target)
    report = scan(path, load_target(path))
    _emit(report, path.name, args.json)
    return exit_status(report)


def _cmd_evaluate(args: argparse.Namespace) -> int:
    registry = yaml.safe_load((ROOT / "benchmarks" / "scenarios.yaml").read_text())
    failed = 0
    total_prose = 0
    negative_subjects = 0
    covered_elsewhere = 0
    false_positives: list[str] = []
    for entry in registry.get("scenarios") or []:
        if entry["status"] != "recorded":
            print(f"skip  {entry['slug']}  ({entry['status']})")
            continue
        path = ROOT / str(entry["path"])
        scenario = load_scenario(path, str(entry["slug"]))
        for name in variants_of(path):
            report = verify(scenario, load_variant(path, name))
            result = score(report, path / name, str(entry["slug"]), name)
            total_prose += result.unchecked_prose
            negative_subjects += result.negative_subjects
            covered_elsewhere += result.covered_elsewhere
            false_positives += [f"{entry['slug']}/{name}:{s}" for s in result.false_positives]
            if result.passed:
                print(f"ok    {entry['slug']}/{name}  ({result.checked} checks)")
            else:
                failed += 1
                print(f"FAIL  {entry['slug']}/{name}")
                for problem in result.problems:
                    print(f"        {problem}")
    # Precision, with its denominator stated. A false-positive rate quoted without the number of
    # subjects it was measured over says nothing: 0 of 3 and 0 of 3000 are the same figure and not
    # the same evidence, and the first is what this corpus currently supports.
    print(
        f"\nfalse positives: {len(false_positives)} of {negative_subjects} negative-set subjects"
        + (f" -- {', '.join(false_positives)}" if false_positives else "")
    )
    print(
        f"{covered_elsewhere} further negative-set entries assert a visibility outcome rather than "
        f"the absence of a finding; expected-visibility.yaml checks those exhaustively."
    )
    print(
        f"{total_prose} further negative-set entries are prose and are not machine-checked; "
        f"this tool emits no narrative claims, so they are vacuously satisfied rather than verified."
    )
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="tearline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ver = sub.add_parser("verify", help="verify one scenario variant")
    ver.add_argument("scenario")
    ver.add_argument("--variant", default="faulted")
    ver.add_argument("--json", action="store_true", help="emit the report as JSON, ids only")
    ver.set_defaults(func=_cmd_verify)
    sc = sub.add_parser("scan", help="verify a real index against a real source system")
    sc.add_argument("target", help="directory holding target.yaml and shared/")
    sc.add_argument("--json", action="store_true", help="emit the report as JSON, ids only")
    sc.set_defaults(func=_cmd_scan)
    ev = sub.add_parser("evaluate", help="score every registered scenario variant")
    ev.set_defaults(func=_cmd_evaluate)
    args = parser.parse_args()
    return int(args.func(args))
