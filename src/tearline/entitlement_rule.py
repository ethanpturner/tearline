"""The entitlement rule a source system states, loaded from its fixture (DEC-012, DEC-021).

DEC-012 forbids a default predicate: the tool evaluates the rule the fixture states. DEC-021 fixes
the form that statement takes -- three named clauses and a named combinator, each from a closed set,
for the same reason DEC-013 closes the enforcement models. A rule expressive enough to say anything
lets the fixture author write both the bug and the expectation, and the scenario proves nothing.

The vocabularies cover the variations DEC-012 names as the reason the rule cannot be hardcoded:
roles additive or required-intersection, direct grants unioned or overriding, tenancy scoped or not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tearline.domain import Entitlement, EntitlementState, Principal


class RuleError(ValueError):
    """The fixture's rule is missing, or names a clause outside the closed set."""


#: How the tenant clause reads a chunk's tenant set.
TENANT_CLAUSES = frozenset({"member", "member-or-unrestricted", "ignored"})
#: How the role clause reads a chunk's role set. `subset` is the required-intersection form: the
#: principal must hold every role the chunk names, not merely one of them.
ROLE_CLAUSES = frozenset({"intersects", "intersects-or-everyone", "subset", "ignored"})
#: How a direct principal grant is read.
DIRECT_CLAUSES = frozenset({"principal-listed", "ignored"})
#: How the three clauses combine. Spelled as the expression rather than named, so that a fixture
#: states the semantics a reader can check instead of a label they must look up.
COMBINATORS = frozenset(
    {
        "tenant AND (role OR direct)",
        "tenant AND role",
        "tenant AND role AND direct",
        "tenant OR role",
        "(tenant OR direct) AND role",
    }
)


def _tenant(clause: str, ent: Entitlement, principal: Principal) -> bool:
    if clause == "ignored":
        return True
    if not ent.tenants:
        return clause == "member-or-unrestricted"
    return principal.tenant in ent.tenants


def _role(clause: str, ent: Entitlement, principal: Principal) -> bool:
    if clause == "ignored":
        return True
    if not ent.roles:
        return False
    if clause == "intersects-or-everyone" and "everyone" in ent.roles:
        return True
    if clause == "subset":
        return ent.roles <= principal.roles
    return bool(ent.roles & principal.roles)


def _direct(clause: str, ent: Entitlement, principal: Principal) -> bool:
    if clause == "ignored":
        return False
    return principal.id in ent.principals


@dataclass(frozen=True)
class EntitlementRule:
    """A source system's stated entitlement semantics."""

    system: str
    tenant: str
    role: str
    direct: str
    combine: str

    def entitled(self, ent: Entitlement, principal: Principal) -> bool:
        """Whether the source system would grant `principal` access to `ent`.

        An `unknown` entitlement grants nothing (DEC-003) whatever the rule says: the rule
        describes how a *stated* permission is read, and there is nothing here to read.
        """
        if ent.state is not EntitlementState.STATED:
            return False
        return self._combine(
            _tenant(self.tenant, ent, principal),
            _role(self.role, ent, principal),
            _direct(self.direct, ent, principal),
        )

    def admitted_by_naive_filter(self, ent: Entitlement, principal: Principal) -> bool:
        """Admit unless a stated restriction excludes the principal -- the bug DEC-003 names.

        The same clauses, read with `state` never consulted and an empty set read as unrestricted,
        so a chunk carrying no tenant and no role is admitted to everyone. Derived from the stated
        rule rather than hardcoded: the defect is *this system's* rule applied to absent data, and
        against a system whose roles are required-intersection it admits a different set.
        """
        tenant = _tenant(
            "member-or-unrestricted" if self.tenant != "ignored" else "ignored", ent, principal
        )
        role = True if not ent.roles else _role(self.role, ent, principal)
        return self._combine(tenant, role, _direct(self.direct, ent, principal))

    def _combine(self, tenant: bool, role: bool, direct: bool) -> bool:
        match self.combine:
            case "tenant AND (role OR direct)":
                return tenant and (role or direct)
            case "tenant AND role":
                return tenant and role
            case "tenant AND role AND direct":
                return tenant and role and direct
            case "tenant OR role":
                return tenant or role
            case "(tenant OR direct) AND role":
                return (tenant or direct) and role
        raise RuleError(f"unknown combinator {self.combine!r}")


def _clause(raw: dict[str, Any], key: str, allowed: frozenset[str]) -> str:
    value = raw.get(key)
    if value is None:
        raise RuleError(f"the rule states no {key} clause; DEC-012 has no default to fall back to")
    if value not in allowed:
        raise RuleError(f"{key} clause {value!r} is not one of {sorted(allowed)} (DEC-021)")
    return str(value)


def load_rule(path: Path) -> EntitlementRule:
    """Read `shared/entitlement-rule.yaml`. Absence is an error, never a default (DEC-012)."""
    if not path.exists():
        raise RuleError(
            f"{path} is missing. DEC-012: the tool has no default predicate, so a scenario that "
            "does not state its source system's entitlement rule cannot be verified."
        )
    raw = yaml.safe_load(path.read_text()) or {}
    rule = raw.get("rule")
    if not isinstance(rule, dict):
        raise RuleError(f"{path} has no `rule:` mapping")
    combine = rule.get("combine")
    if combine not in COMBINATORS:
        raise RuleError(f"combinator {combine!r} is not one of {sorted(COMBINATORS)} (DEC-021)")
    return EntitlementRule(
        system=str(raw.get("system", "unknown")),
        tenant=_clause(rule, "tenant", TENANT_CLAUSES),
        role=_clause(rule, "role", ROLE_CLAUSES),
        direct=_clause(rule, "direct", DIRECT_CLAUSES),
        combine=str(combine),
    )
