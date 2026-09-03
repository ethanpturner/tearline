"""tearline — retrieval entitlement verification."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tearline.evaluate import score
from tearline.fixtures import load_scenario, load_variant, variants_of
from tearline.verify import verify

ROOT = Path(__file__).resolve().parent.parent.parent


def _cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.scenario)
    scenario = load_scenario(path, path.name)
    variant = load_variant(path, args.variant)
    report = verify(scenario, variant)
    print(
        f"{path.name}/{args.variant}: {report.chunks_examined} chunks, "
        f"{report.chunks_untraceable} untraceable, partial={report.partial}"
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
    for skipped in report.probes_skipped:
        print(
            f"  not-run         {skipped}: fewer than two identities; nothing about the boundary "
            f"was exercised"
        )
    return 1 if (report.propagation or report.partial) else 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    registry = yaml.safe_load((ROOT / "benchmarks" / "scenarios.yaml").read_text())
    failed = 0
    total_prose = 0
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
            if result.passed:
                print(f"ok    {entry['slug']}/{name}  ({result.checked} checks)")
            else:
                failed += 1
                print(f"FAIL  {entry['slug']}/{name}")
                for problem in result.problems:
                    print(f"        {problem}")
    print(
        f"\n{total_prose} negative-set entries are prose and are not machine-checked; "
        f"this tool emits no narrative claims, so they are vacuously satisfied rather than verified."
    )
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="tearline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ver = sub.add_parser("verify", help="verify one scenario variant")
    ver.add_argument("scenario")
    ver.add_argument("--variant", default="faulted")
    ver.set_defaults(func=_cmd_verify)
    ev = sub.add_parser("evaluate", help="score every registered scenario variant")
    ev.set_defaults(func=_cmd_evaluate)
    args = parser.parse_args()
    return int(args.func(args))
