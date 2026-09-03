"""Verification: propagation, drift, and differential retrieval."""

from __future__ import annotations

from tearline.domain import (
    Chunk,
    Entitlement,
    MismatchCause,
    Principal,
    ProbeOutcome,
    ProbeResult,
    PropagationFinding,
    SourceDocument,
    Verdict,
    VerificationReport,
)
from tearline.fixtures import Scenario, Variant
from tearline.rules import ENFORCEMENT_MODELS, entitled_by_all, entitled_by_rule, safe_bound


def _cause_from_timestamps(chunk: Chunk, sources: list[SourceDocument]) -> MismatchCause:
    """Drift and propagation fault need different people to fix them (DEC-006). Where the
    timestamps cannot separate them the cause is `undetermined` and is never guessed."""
    acl_times = [d.acl_modified_at for d in sources if d.acl_modified_at is not None]
    if chunk.ingested_at is None or len(acl_times) != len(sources) or not acl_times:
        return MismatchCause.UNDETERMINED
    return (
        MismatchCause.DRIFT
        if max(acl_times) > chunk.ingested_at
        else MismatchCause.PROPAGATION_FAULT
    )


def _same(a: Entitlement, b: Entitlement) -> bool:
    return (a.state, a.tenants, a.roles, a.principals) == (
        b.state,
        b.tenants,
        b.roles,
        b.principals,
    )


def _within_bound(tag: Entitlement, bound: Entitlement, principals: list[Principal]) -> bool:
    """Whether the tag grants to nobody the bound excludes.

    Evaluated over the identities under test rather than universally: a general subset check would
    need a principal universe the fixture does not define. The scope is stated in the output.
    """
    return all(not entitled_by_rule(tag, p) or entitled_by_rule(bound, p) for p in principals)


def check_propagation(scenario: Scenario, variant: Variant) -> tuple[list[PropagationFinding], int]:
    findings: list[PropagationFinding] = []
    untraceable = 0

    for chunk in variant.chunks.values():
        sources = [
            scenario.documents[d] for d in chunk.source_document_ids if d in scenario.documents
        ]
        if not sources:
            untraceable += 1
            findings.append(
                PropagationFinding(
                    chunk_id=chunk.id,
                    verdict=Verdict.UNVERIFIABLE,
                    cause=MismatchCause.UNDETERMINED,
                    observed=chunk.entitlement,
                    expected=None,
                    detail=(
                        "no source document, so there is no ACL to compare against. The tag may be "
                        "correct; nothing available establishes that."
                    ),
                )
            )
            continue

        if len(sources) == 1:
            expected = sources[0].entitlement
            if _same(chunk.entitlement, expected):
                continue
            findings.append(
                PropagationFinding(
                    chunk_id=chunk.id,
                    verdict=Verdict.CONTRADICTED,
                    cause=_cause_from_timestamps(chunk, sources),
                    observed=chunk.entitlement,
                    expected=expected,
                )
            )
            continue

        # Several sources: the source system has never had an opinion about an object made from
        # more than one of them, so the correct tag is a policy question it has not answered.
        bound = safe_bound([d.entitlement for d in sources])
        assert bound is not None
        principals = list(scenario.principals.values())
        if _within_bound(chunk.entitlement, bound, principals):
            findings.append(
                PropagationFinding(
                    chunk_id=chunk.id,
                    verdict=Verdict.UNVERIFIABLE,
                    cause=MismatchCause.INDETERMINATE_SOURCE,
                    observed=chunk.entitlement,
                    expected=bound,
                    detail=(
                        "sources diverge and the tag discloses nothing beyond what all of them "
                        "permit. Not a claim that the tag is correct: the organisation may "
                        "legitimately have decided otherwise, and the source has not recorded it."
                    ),
                )
            )
        else:
            findings.append(
                PropagationFinding(
                    chunk_id=chunk.id,
                    verdict=Verdict.CONTRADICTED,
                    cause=MismatchCause.EXCEEDS_SAFE_BOUND,
                    observed=chunk.entitlement,
                    expected=bound,
                    detail=(
                        "the tag grants beyond what every source permits. The correct entitlement "
                        "is still undetermined; that this one is wrong is not."
                    ),
                )
            )
    return findings, untraceable


def run_probes(scenario: Scenario, variant: Variant) -> tuple[list[ProbeResult], list[str]]:
    enforce = ENFORCEMENT_MODELS[variant.enforcement]
    results: list[ProbeResult] = []
    skipped: list[str] = []

    for probe in scenario.probes:
        if not probe.runnable:
            # DEC-007: a single identity's results establish nothing about a boundary.
            skipped.append(probe.id)
            continue
        candidates = probe.matches[: variant.ann_limit] if variant.ann_limit else probe.matches
        for pid in probe.principals:
            principal = scenario.principals[pid]
            returned, truth = [], set()
            for cid in probe.matches:
                chunk = variant.chunks[cid]
                sources = [
                    scenario.documents[d]
                    for d in chunk.source_document_ids
                    if d in scenario.documents
                ]
                if entitled_by_all([s.entitlement for s in sources], principal):
                    truth.add(cid)
                if cid in candidates and enforce(chunk.entitlement, principal):
                    returned.append(cid)
            over = frozenset(returned) - truth
            under = frozenset(truth) - frozenset(returned)
            outcome = (
                ProbeOutcome.BOTH
                if over and under
                else ProbeOutcome.OVER_RETRIEVAL
                if over
                else ProbeOutcome.UNDER_RETRIEVAL
                if under
                else ProbeOutcome.CLEAN
            )
            results.append(
                ProbeResult(
                    probe_id=probe.id,
                    principal_id=pid,
                    returned=tuple(returned),
                    over_retrieved=over,
                    under_retrieved=under,
                    verdict=Verdict.CONTRADICTED if (over or under) else Verdict.VERIFIED,
                    outcome=outcome,
                )
            )
    return results, skipped


def verify(scenario: Scenario, variant: Variant) -> VerificationReport:
    findings, untraceable = check_propagation(scenario, variant)
    probes, skipped = run_probes(scenario, variant)
    return VerificationReport(
        chunks_examined=len(variant.chunks),
        chunks_untraceable=untraceable,
        propagation=tuple(findings),
        probes=tuple(probes),
        probes_skipped=tuple(skipped),
        # A skipped probe means a boundary was never exercised; the report must say so (DEC-007).
        partial=bool(skipped),
    )
