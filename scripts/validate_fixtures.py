"""Check that a scenario's authored expectations agree with its own fixture.

The expected-visibility files are hand-authored, and hand-authored set arithmetic is wrong more
often than anyone admits. This recomputes visibility from the fixture -- documents, index,
principals, probes, and the scenario's stated entitlement rule -- and compares it to what was
written down.

It does not test the tool. It tests the scenario, so that a failing run means the tool is wrong
rather than the answer key.

Exit codes: 0 all scenarios internally consistent; 1 a disagreement; 2 a fixture is unreadable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS = ROOT / "benchmarks"


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def entitled(chunk: dict[str, Any], principal: dict[str, Any]) -> bool:
    """The `fixture-kb` rule: tenant AND (role OR direct). See shared/entitlement-rule.yaml."""
    ent = chunk["entitlement"]
    if ent.get("state") != "stated":
        # An unknown entitlement is never a grant (DEC-003).
        return False
    if principal.get("tenant") not in (ent.get("tenants") or []):
        return False
    roles = set(ent.get("roles") or [])
    by_role = bool(roles & set(principal.get("roles") or [])) or "everyone" in roles
    by_direct = principal["id"] in (ent.get("principals") or [])
    return by_role or by_direct


def check_variant(scenario: Path, variant: str) -> list[str]:
    shared = scenario / "shared"
    principals = {p["id"]: p for p in load(shared / "principals.yaml")["principals"]}
    probes = load(shared / "probes.yaml")["probes"]
    chunks = {c["id"]: c for c in load(scenario / variant / "index.yaml")["chunks"]}
    expected = load(scenario / variant / "expected-visibility.yaml")["visibility"]

    computed: dict[tuple[str, str], set[str]] = {}
    for probe in probes:
        for pid in probe["principals"]:
            visible = {c for c in probe["matches"] if entitled(chunks[c], principals[pid])}
            computed[(probe["id"], pid)] = visible

    problems: list[str] = []
    seen = set()
    for row in expected:
        key = (row["probe"], row["principal"])
        seen.add(key)
        if key not in computed:
            problems.append(f"{variant}: {key} is expected but the probe does not run it")
            continue
        if set(row["visible"]) != computed[key]:
            problems.append(
                f"{variant}: {key} expected visible={sorted(row['visible'])} "
                f"but the fixture's own rule gives {sorted(computed[key])}"
            )
    for key in computed.keys() - seen:
        problems.append(f"{variant}: {key} is produced by the fixture but has no expected row")
    return problems


def main() -> int:
    registry = load(BENCHMARKS / "scenarios.yaml")
    scenarios = registry.get("scenarios") or []
    if not scenarios:
        print("no scenarios registered")
        return 0

    failed = 0
    for entry in scenarios:
        path = ROOT / entry["path"]
        if entry["status"] != "recorded":
            print(f"skip  {entry['slug']} (status: {entry['status']})")
            continue
        problems: list[str] = []
        for variant in ("clean", "faulted"):
            if (path / variant).is_dir():
                problems += check_variant(path, variant)
        if problems:
            failed += 1
            print(f"FAIL  {entry['slug']}")
            for p in problems:
                print(f"        {p}")
        else:
            print(f"ok    {entry['slug']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
