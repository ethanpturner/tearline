"""The entitlement predicates, and the failure DEC-003 exists to make unrepresentable."""

from __future__ import annotations

import pytest

from tearline.domain import Entitlement, EntitlementState, Principal
from tearline.entitlement_rule import EntitlementRule
from tearline.rules import safe_bound

#: The rule every fixture in `benchmarks/` states. Named here so the tests below read the same
#: predicate the tool does, rather than a copy that could drift from it.
FIXTURE_RULE = EntitlementRule(
    system="fixture-kb",
    tenant="member",
    role="intersects-or-everyone",
    direct="principal-listed",
    combine="tenant AND (role OR direct)",
)
entitled_by_rule = FIXTURE_RULE.entitled
admitted_by_naive_filter = FIXTURE_RULE.admitted_by_naive_filter

ACME_ENG = Principal(id="p1", label="acme eng", tenant="acme", roles=frozenset({"employee"}))
GLOBEX_ENG = Principal(id="p2", label="globex eng", tenant="globex", roles=frozenset({"employee"}))
ACME_FIN = Principal(
    id="p3", label="acme fin", tenant="acme", roles=frozenset({"employee", "finance"})
)


def stated(tenants: set[str], roles: set[str]) -> Entitlement:
    return Entitlement(
        state=EntitlementState.STATED, tenants=frozenset(tenants), roles=frozenset(roles)
    )


def test_there_is_no_permissive_state() -> None:
    """The model must not offer a way to record absence as a grant (DEC-003)."""
    assert {e.value for e in EntitlementState} == {"stated", "unknown"}


def test_unknown_grants_nothing_under_the_rule() -> None:
    assert not entitled_by_rule(Entitlement(state=EntitlementState.UNKNOWN), ACME_ENG)


def test_the_naive_filter_admits_an_untagged_chunk_to_everyone() -> None:
    """The bug DEC-003 names, reproduced: absence read as no restriction."""
    untagged = Entitlement(state=EntitlementState.UNKNOWN)
    assert admitted_by_naive_filter(untagged, ACME_ENG)
    assert admitted_by_naive_filter(untagged, GLOBEX_ENG)


def test_roles_are_an_intersection_not_an_exact_match() -> None:
    """A principal holding more roles than a chunk requires is still entitled."""
    assert entitled_by_rule(stated({"acme"}, {"finance"}), ACME_FIN)


def test_everyone_is_a_stated_role_not_an_absence() -> None:
    assert entitled_by_rule(stated({"acme", "globex"}, {"everyone"}), GLOBEX_ENG)


def test_empty_tenants_is_not_all_tenants() -> None:
    assert not entitled_by_rule(stated(set(), {"everyone"}), ACME_ENG)


@pytest.mark.parametrize("principal", [ACME_ENG, GLOBEX_ENG, ACME_FIN])
def test_safe_bound_is_the_intersection(principal: Principal) -> None:
    """A chunk contains material from all its sources (DEC-015)."""
    bound = safe_bound([stated({"acme", "globex"}, {"everyone"}), stated({"acme"}, {"everyone"})])
    assert bound is not None
    assert entitled_by_rule(bound, principal) == (principal.tenant == "acme")


def test_safe_bound_of_nothing_is_none_not_unrestricted() -> None:
    assert safe_bound([]) is None
