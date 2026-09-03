"""Check that a scenario's authored expectations agree with its own fixture.

Recomputes, for every (probe, principal):

  truth    what the principal is entitled to, from the SOURCE DOCUMENTS via the scenario's stated
           entitlement rule (DEC-005, DEC-012)
  visible  what the variant's declared enforcement returns, from the INDEX
  deltas   over-retrieval (visible minus truth) and under-retrieval (truth minus visible), matched
           against the probe's relevance set (DEC-008, DEC-011)

and compares all three to the authored `expected-visibility.yaml`.

It does not test the tool. It tests the scenario, so that a failing run means the tool is wrong
rather than the answer key. Hand-authored set arithmetic is wrong more often than anyone admits.

Exit codes: 0 consistent; 1 a disagreement; 2 a fixture is unreadable.
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


def _tenant_ok(ent: dict[str, Any], principal: dict[str, Any], *, empty_is_unrestricted: bool) -> bool:
    tenants = ent.get("tenants") or []
    if not tenants:
        return empty_is_unrestricted
    return principal.get("tenant") in tenants


def _role_ok(ent: dict[str, Any], principal: dict[str, Any], *, empty_is_unrestricted: bool) -> bool:
    roles = set(ent.get("roles") or [])
    if not roles:
        return empty_is_unrestricted
    if "everyone" in roles:
        return True
    if roles & set(principal.get("roles") or []):
        return True
    return principal["id"] in (ent.get("principals") or [])


def entitled_by_rule(ent: dict[str, Any], principal: dict[str, Any]) -> bool:
    """The stated rule: tenant AND (role OR direct). An `unknown` entitlement grants nothing."""
    if ent.get("state") != "stated":
        return False  # DEC-003: absence is never a grant.
    return _tenant_ok(ent, principal, empty_is_unrestricted=False) and _role_ok(
        ent, principal, empty_is_unrestricted=False
    )


def admitted_by_naive_filter(ent: dict[str, Any], principal: dict[str, Any]) -> bool:
    """A chunk is admitted unless a stated restriction explicitly excludes the principal.

    The bug DEC-003 names: an absent restriction is read as no restriction, so a chunk carrying no
    tenant and no role is admitted to everyone. `state` is not consulted at all -- the filter never
    asks whether the metadata is present, only whether it excludes.
    """
    return _tenant_ok(ent, principal, empty_is_unrestricted=True) and _role_ok(
        ent, principal, empty_is_unrestricted=True
    )


FILTERS = {"rule": entitled_by_rule, "naive-tenant-exclusion": admitted_by_naive_filter}


def check_variant(scenario: Path, variant: str) -> list[str]:
    shared = scenario / "shared"
    documents = {d["id"]: d for d in load(shared / "documents.yaml")["documents"]}
    principals = {p["id"]: p for p in load(shared / "principals.yaml")["principals"]}
    probes = load(shared / "probes.yaml")["probes"]

    index = load(scenario / variant / "index.yaml")
    chunks = {c["id"]: c for c in index["chunks"]}
    filter_name = index.get("filter", "rule")
    if filter_name not in FILTERS:
        return [f"{variant}: unknown filter {filter_name!r}; known: {sorted(FILTERS)}"]
    enforce = FILTERS[filter_name]

    expected = load(scenario / variant / "expected-visibility.yaml")["visibility"]
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()

    for probe in probes:
        for pid in probe["principals"]:
            principal = principals[pid]
            matched = probe["matches"]
            truth, visible = set(), set()
            for cid in matched:
                chunk = chunks[cid]
                sources = [documents[d] for d in chunk.get("source_document_ids") or [] if d in documents]
                # A chunk drawn from several documents contains material from every one of them,
                # so a principal may see it only if entitled by ALL of its sources (DEC-015). With
                # a single source this is the ordinary case. With none, the chunk is untraceable
                # and contributes to no truth set.
                if sources and all(entitled_by_rule(d["entitlement"], principal) for d in sources):
                    truth.add(cid)
                if enforce(chunk["entitlement"], principal):
                    visible.add(cid)

            row = next((r for r in expected if r["probe"] == probe["id"] and r["principal"] == pid), None)
            seen.add((probe["id"], pid))
            if row is None:
                problems.append(f"{variant}: ({probe['id']}, {pid}) has no expected row")
                continue
            for label, actual in (
                ("visible", visible),
                ("over_retrieved", visible - truth),
                ("under_retrieved", truth - visible),
            ):
                if set(row.get(label) or []) != actual:
                    problems.append(
                        f"{variant}: ({probe['id']}, {pid}) {label} authored="
                        f"{sorted(row.get(label) or [])} fixture gives {sorted(actual)}"
                    )

    for row in expected:
        if (row["probe"], row["principal"]) not in seen:
            problems.append(f"{variant}: ({row['probe']}, {row['principal']}) is expected but never run")
    return problems


def main() -> int:
    scenarios = load(BENCHMARKS / "scenarios.yaml").get("scenarios") or []
    if not scenarios:
        print("no scenarios registered")
        return 0

    failed = 0
    for entry in scenarios:
        path = ROOT / entry["path"]
        if entry["status"] != "recorded":
            print(f"skip  {entry['slug']} (status: {entry['status']})")
            continue
        variants = sorted(d.name for d in path.iterdir() if d.is_dir() and (d / "index.yaml").exists())
        problems: list[str] = []
        for variant in variants:
            problems += check_variant(path, variant)
        if problems:
            failed += 1
            print(f"FAIL  {entry['slug']}")
            for p in problems:
                print(f"        {p}")
        else:
            print(f"ok    {entry['slug']}  ({', '.join(variants)})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
