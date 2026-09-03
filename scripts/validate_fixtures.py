"""Check that a scenario's authored expectations agree with the entitlement rule.

This predates the package and once carried its own copy of the rule. It now imports from
`tearline.rules`, because two implementations of the same predicate is a hazard: they drift, and
the drift shows up as confident disagreement between the fixture checker and the tool.

It remains useful for a narrower job than `tearline evaluate`. This checks that a hand-authored
`expected-visibility.yaml` is arithmetically consistent with the fixture -- the thing worth running
while *writing* a scenario, before there is any question of whether the tool implements it.
`tearline evaluate` checks the tool against those expectations.

Exit codes: 0 consistent; 1 a disagreement.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from tearline.fixtures import load_scenario, load_variant, variants_of
from tearline.rules import enforcement_for, entitled_by_all

ROOT = Path(__file__).resolve().parent.parent


def check(path: Path, slug: str, variant_name: str) -> list[str]:
    scenario = load_scenario(path, slug)
    variant = load_variant(path, variant_name)
    enforce = enforcement_for(scenario.rule, variant.enforcement)
    expected_doc = yaml.safe_load((path / variant_name / "expected-visibility.yaml").read_text())
    expected = {(r["probe"], r["principal"]): r for r in expected_doc.get("visibility") or []}

    problems: list[str] = []
    skipped = {p.id for p in scenario.probes if not p.runnable}
    if skipped != set(expected_doc.get("probes_skipped") or []):
        problems.append(
            f"{variant_name}: probes that cannot run are {sorted(skipped)} but the file declares "
            f"{sorted(expected_doc.get('probes_skipped') or [])}"
        )

    seen = set()
    for probe in scenario.probes:
        if not probe.runnable:
            continue
        candidates = probe.matches[: variant.ann_limit] if variant.ann_limit else probe.matches
        for pid in probe.principals:
            principal = scenario.principals[pid]
            truth, visible, undetermined = set(), set(), set()
            for cid in probe.matches:
                chunk = variant.chunks[cid]
                sources = [
                    scenario.documents[d]
                    for d in chunk.source_document_ids
                    if d in scenario.documents
                ]
                if not sources:
                    # No source document, so nothing establishes that receiving this chunk was
                    # permitted -- and nothing establishes that it was not (DEC-022). It belongs
                    # to neither the truth set nor the leak set. Computed here independently of
                    # the tool, because a validator sharing the tool's logic validates nothing.
                    undetermined.add(cid)
                elif entitled_by_all(scenario.rule, [s.entitlement for s in sources], principal):
                    truth.add(cid)
                if cid in candidates and enforce(chunk.entitlement, principal):
                    visible.add(cid)
            key = (probe.id, pid)
            seen.add(key)
            row = expected.get(key)
            if row is None:
                problems.append(f"{variant_name}: {key} produced by the fixture but not expected")
                continue
            for label, actual in (
                ("visible", visible),
                ("over_retrieved", visible - truth - undetermined),
                ("under_retrieved", truth - visible),
                ("undetermined_returned", visible & undetermined),
            ):
                if set(row.get(label) or []) != actual:
                    problems.append(
                        f"{variant_name}: {key} {label} authored={sorted(row.get(label) or [])} "
                        f"fixture gives {sorted(actual)}"
                    )
    for key in set(expected) - seen:
        problems.append(f"{variant_name}: {key} is expected but never run")
    return problems


def main() -> int:
    registry = yaml.safe_load((ROOT / "benchmarks" / "scenarios.yaml").read_text())
    failed = 0
    for entry in registry.get("scenarios") or []:
        if entry["status"] != "recorded":
            print(f"skip  {entry['slug']} ({entry['status']})")
            continue
        path = ROOT / str(entry["path"])
        problems: list[str] = []
        for variant in variants_of(path):
            problems += check(path, str(entry["slug"]), variant)
        if problems:
            failed += 1
            print(f"FAIL  {entry['slug']}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {entry['slug']}  ({', '.join(variants_of(path))})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
