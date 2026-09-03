"""The data model, held against the document that defines it.

`data-model.md` is authoritative for field names and types. Authoritative is a claim about process,
not a property of a Markdown file, so this test makes it one: the field tables are parsed and
compared against the classes in both directions. A rename in the document alone fails, and so does a
field the document never sanctioned.

The rest of the tests here pin properties the decision log states as absolute -- that no object can
hold chunk text, that nothing is mutable, that there is no permissive entitlement state. Each is a
thing the model must *not* be able to express, and a constraint of that shape is only real if
something tries to violate it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from tearline import domain
from tearline.domain import (
    Chunk,
    Entitlement,
    EntitlementState,
    Principal,
    ProbeResult,
    Verdict,
    VerificationReport,
)

DOC = Path(__file__).resolve().parents[2] / "docs" / "architecture" / "data-model.md"
#: Words that would mark a field as carrying chunk text. DEC-002 forbids one existing at all.
CONTENT_WORDS = ("text", "content", "body", "excerpt", "snippet", "passage", "payload")


def _documented_fields() -> dict[str, set[str]]:
    """Every `## N. \\`Object\\`` heading and the field names in the table beneath it."""
    sections: dict[str, set[str]] = {}
    current: str | None = None
    for line in DOC.read_text().splitlines():
        heading = re.match(r"^## \d+\. `(\w+)`", line)
        if heading:
            current = heading.group(1)
            sections[current] = set()
            continue
        if current and line.startswith("| `"):
            sections[current].add(line.split("`")[1])
    return {name: fields for name, fields in sections.items() if fields}


DOCUMENTED = _documented_fields()


def test_the_document_describes_objects_that_exist() -> None:
    assert DOCUMENTED, "no field tables parsed; the document's shape changed"
    for name in DOCUMENTED:
        assert hasattr(domain, name), f"data-model.md section for {name}, which does not exist"


@pytest.mark.parametrize("name", sorted(DOCUMENTED))
def test_the_fields_agree_in_both_directions(name: str) -> None:
    """Both directions, because each catches a different mistake. A documented field the code lacks
    is a spec nobody implemented; an undocumented field the code has is a decision nobody wrote
    down -- and this model's fields encode decisions about what may be asserted."""
    model = getattr(domain, name)
    actual = set(model.model_fields)
    assert actual == DOCUMENTED[name], (
        f"{name}: only in code {sorted(actual - DOCUMENTED[name])}, "
        f"only in data-model.md {sorted(DOCUMENTED[name] - actual)}"
    )


def test_no_object_can_hold_chunk_content() -> None:
    """DEC-002, as a property of the model rather than a habit of its callers.

    A report about a confidentiality failure is pasted into tickets and CI logs, which have weaker
    controls than the index it came from. If no field can hold content, no report can leak it.
    """
    for name in DOCUMENTED:
        for field in getattr(domain, name).model_fields:
            for word in CONTENT_WORDS:
                assert word not in field.lower(), f"{name}.{field} may hold content (DEC-002)"


def test_there_is_no_permissive_entitlement_state() -> None:
    """DEC-003. `unknown` must not be expressible as a grant, so the enum offers no `public`,
    `open`, or `all` to record absence as permission."""
    values = {s.value for s in EntitlementState}
    assert values == {"stated", "unknown"}, values


def test_a_verdict_is_three_valued() -> None:
    """DEC-001. The third value is the whole point: a boolean would put "not determined" on the
    same axis as "not true", which is the collapse every scenario in the corpus is built around."""
    assert {v.value for v in Verdict} == {"verified", "contradicted", "unverifiable"}


def test_objects_are_frozen() -> None:
    principal = Principal(id="p", label="p")
    with pytest.raises(ValidationError):
        principal.id = "other"  # type: ignore[misc]


def test_an_unknown_field_is_refused() -> None:
    """`extra="forbid"`, so an object carrying an invented field fails validation instead of
    passing downstream stripped of it and looking valid."""
    with pytest.raises(ValidationError):
        Principal(id="p", label="p", clearance="top-secret")  # type: ignore[call-arg]


def test_an_intersection_with_an_unknown_is_unknown() -> None:
    """DEC-015 through DEC-003: a safe bound drawn from something unstated is not a narrow grant,
    it is no information. Returning a stated-but-empty entitlement here would turn absence into a
    positive claim about what the chunk requires."""
    stated = Entitlement(state=EntitlementState.STATED, tenants=frozenset({"acme"}))
    bound = stated.intersect(Entitlement(state=EntitlementState.UNKNOWN))
    assert bound.state is EntitlementState.UNKNOWN
    assert bound.tenants == frozenset()


def test_roles_union_when_one_side_states_none() -> None:
    """An empty role set is not a restriction to nothing; it is silence about roles. Intersecting
    with it would narrow the bound on the strength of a fact nobody recorded."""
    a = Entitlement(state=EntitlementState.STATED, tenants=frozenset({"acme"}))
    b = Entitlement(
        state=EntitlementState.STATED,
        tenants=frozenset({"acme"}),
        roles=frozenset({"finance"}),
    )
    assert a.intersect(b).roles == frozenset({"finance"})


def test_a_report_defaults_to_saying_no_store_was_asked() -> None:
    """`simulated` is the default rather than a backend name, so a report built without a store
    cannot silently read as evidence that a real index applies the boundary."""
    report = VerificationReport(
        chunks_examined=0,
        chunks_untraceable=0,
        propagation=(),
        probes=(),
        probes_skipped=(),
        partial=False,
    )
    assert report.enforcement_site == "simulated"


def test_the_undetermined_axis_is_separate_from_the_leak_count() -> None:
    """DEC-022. Defaulting `undetermined_returned` to empty is what lets every existing caller keep
    working; keeping it off `over_retrieved` is what stops an ingestion gap reading as a breach."""
    assert "undetermined_returned" in ProbeResult.model_fields
    assert ProbeResult.model_fields["undetermined_returned"].default == frozenset()
    assert "undetermined" not in {f for f in Chunk.model_fields}
