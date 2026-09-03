"""The rule comes from the fixture and nowhere else (DEC-012, DEC-021).

The point of these tests is not that the loader parses YAML. It is that the tool has no predicate of
its own: change the stated rule and the same chunk and principal get a different answer, and remove
it and nothing runs at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tearline.domain import Entitlement, EntitlementState, Principal
from tearline.entitlement_rule import EntitlementRule, RuleError, load_rule
from tearline.fixtures import load_scenario

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmarks" / "wrong-tenant-tag"

#: Entitled under the fixture rule by tenancy and the `engineering` role.
CHUNK = Entitlement(
    state=EntitlementState.STATED,
    tenants=frozenset({"acme"}),
    roles=frozenset({"engineering", "finance"}),
)
ALICE = Principal(id="p-alice", label="Alice", tenant="acme", roles=frozenset({"engineering"}))


def _rule(**overrides: str) -> EntitlementRule:
    base = {
        "system": "test",
        "tenant": "member",
        "role": "intersects-or-everyone",
        "direct": "principal-listed",
        "combine": "tenant AND (role OR direct)",
    }
    return EntitlementRule(**{**base, **overrides})


def test_the_stated_rule_decides_and_not_the_tool() -> None:
    """One shared role admits under an additive reading and denies under required-intersection.

    This is the DEC-012 failure in miniature. A tool hardcoding either predicate would report the
    other system's correct index as a finding -- confidently, and about the index rather than about
    its own assumption.
    """
    assert _rule(role="intersects").entitled(CHUNK, ALICE)
    assert not _rule(role="subset").entitled(CHUNK, ALICE)


def test_a_direct_grant_is_read_as_the_rule_says() -> None:
    ent = Entitlement(
        state=EntitlementState.STATED,
        tenants=frozenset({"acme"}),
        roles=frozenset({"legal"}),
        principals=frozenset({"p-alice"}),
    )
    assert _rule().entitled(ent, ALICE)
    assert not _rule(direct="ignored").entitled(ent, ALICE)
    # Overriding tenancy is a different system again, and it is not this one.
    outsider = Principal(id="p-alice", label="Alice", tenant="globex", roles=frozenset())
    assert not _rule().entitled(ent, outsider)
    assert _rule(combine="(tenant OR direct) AND role").entitled(
        Entitlement(
            state=EntitlementState.STATED,
            tenants=frozenset({"acme"}),
            roles=frozenset({"everyone"}),
            principals=frozenset({"p-alice"}),
        ),
        outsider,
    )


def test_an_unknown_entitlement_grants_nothing_whatever_the_rule_says() -> None:
    """DEC-003 sits above the rule: the rule says how a *stated* permission is read."""
    unknown = Entitlement(state=EntitlementState.UNKNOWN)
    for combine in ("tenant AND role", "tenant OR role"):
        assert not _rule(combine=combine, tenant="ignored", role="ignored").entitled(unknown, ALICE)


def test_a_missing_rule_is_an_error_not_a_default(tmp_path: Path) -> None:
    with pytest.raises(RuleError, match="no default predicate"):
        load_rule(tmp_path / "entitlement-rule.yaml")


def test_a_clause_outside_the_closed_set_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "entitlement-rule.yaml"
    path.write_text(
        "system: x\nrule:\n  tenant: whatever-i-like\n  role: intersects\n"
        "  direct: ignored\n  combine: tenant AND role\n"
    )
    with pytest.raises(RuleError, match="DEC-021"):
        load_rule(path)


def test_a_scenario_without_a_rule_will_not_load(tmp_path: Path) -> None:
    """A scenario whose rule is absent fails to load rather than being verified against a guess."""
    shared = tmp_path / "shared"
    shared.mkdir()
    for name in ("documents.yaml", "principals.yaml", "probes.yaml"):
        source = BENCHMARK / "shared" / name
        (shared / name).write_text(source.read_text())
    with pytest.raises(RuleError):
        load_scenario(tmp_path, "no-rule")


def test_the_benchmark_rule_is_the_one_the_scenarios_were_authored_against() -> None:
    rule = load_scenario(BENCHMARK, "wrong-tenant-tag").rule
    assert (rule.system, rule.combine) == ("fixture-kb", "tenant AND (role OR direct)")
