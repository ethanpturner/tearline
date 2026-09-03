"""Verification: propagation, drift, and differential retrieval.

Every predicate here is the one the scenario's fixture states (DEC-012); nothing in this module
knows how a source system combines tenant, role and direct grants.

`run_probes` takes an optional `retrieve`. Supplied, it is a real store answering a real query and
the differential axis observes what that store actually returned; omitted, the same axis is computed
from the fixture's authored `matches`. The two are not equivalent and the report says which ran, via
`enforcement_site`.
"""

from __future__ import annotations

from collections.abc import Callable

from tearline.domain import (
    Chunk,
    Entitlement,
    MismatchCause,
    Principal,
    Probe,
    ProbeOutcome,
    ProbeResult,
    PropagationFinding,
    SourceDocument,
    Verdict,
    VerificationReport,
)
from tearline.fixtures import Scenario, Variant
from tearline.rules import enforcement_for, entitled_by_all, safe_bound

#: Ask a live store what it returns for one probe and one principal: chunk ids, never content
#: (DEC-002). The candidate limit is the variant's `ann_limit`, or `None` for the store's default.
Retrieve = Callable[["Probe", Principal, int | None], list[str]]


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


def _within_bound(
    scenario: Scenario, tag: Entitlement, bound: Entitlement, principals: list[Principal]
) -> bool:
    """Whether the tag grants to nobody the bound excludes.

    Evaluated over the identities under test rather than universally: a general subset check would
    need a principal universe the fixture does not define. The scope is stated in the output.
    """
    entitled = scenario.rule.entitled
    return all(not entitled(tag, p) or entitled(bound, p) for p in principals)


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
        if _within_bound(scenario, chunk.entitlement, bound, principals):
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


def run_probes(
    scenario: Scenario, variant: Variant, retrieve: Retrieve | None = None
) -> tuple[list[ProbeResult], list[str]]:
    """Differential retrieval (DEC-007): the same query under two identities.

    Truth -- what a principal is entitled to -- is computed from the *source system* over the
    probe's full relevance set, never from the index, and never from what the store returned. That
    is what lets a store agreeing with its own wrong tags register as a finding rather than a pass.
    """
    enforce = enforcement_for(scenario.rule, variant.enforcement)
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
            live = None if retrieve is None else retrieve(probe, principal, variant.ann_limit)
            returned: list[str] = []
            truth: set[str] = set()
            undetermined: set[str] = set()
            absent = frozenset(cid for cid in probe.matches if cid not in variant.chunks)
            for cid in probe.matches:
                chunk = variant.chunks.get(cid)
                if chunk is None:
                    # The probe names a chunk the index does not hold. Nothing about entitlement is
                    # determinable for it, and it is not the boundary's failure -- see
                    # `ProbeResult.absent_from_index`. Against a fixture this cannot happen; against
                    # a live index it is how an ingestion gap arrives.
                    continue
                sources = [
                    scenario.documents[d]
                    for d in chunk.source_document_ids
                    if d in scenario.documents
                ]
                if not sources:
                    # No source document, so there is no ACL to compare against and no basis for
                    # calling a return either permitted or not. Held out of both sets below.
                    undetermined.add(cid)
                elif entitled_by_all(scenario.rule, [s.entitlement for s in sources], principal):
                    truth.add(cid)
                if live is None:
                    if cid in candidates and enforce(chunk.entitlement, principal):
                        returned.append(cid)
                elif cid in live:
                    returned.append(cid)
            if live is not None:
                # A live store may return a chunk the probe never listed as relevant. That is not
                # over-retrieval by this tool's definition -- relevance is not under test (DEC-011)
                # -- unless the principal is not entitled to it, which is a disclosure whatever the
                # query meant. So an unlisted chunk is examined and an entitled one is ignored.
                for cid in live:
                    if cid in probe.matches:
                        continue
                    extra = variant.chunks.get(cid)
                    if extra is None:
                        # An id the inventory read never saw -- a stale point, a second collection,
                        # a race with ingestion. Nothing establishes it is entitled and nothing
                        # establishes it is not, so it is `undetermined` for the same reason an
                        # untraceable chunk is, and reported rather than counted as a disclosure.
                        undetermined.add(cid)
                        returned.append(cid)
                        continue
                    extra_sources = [
                        scenario.documents[d]
                        for d in extra.source_document_ids
                        if d in scenario.documents
                    ]
                    if not extra_sources:
                        undetermined.add(cid)
                        returned.append(cid)
                    elif not entitled_by_all(
                        scenario.rule, [s.entitlement for s in extra_sources], principal
                    ):
                        returned.append(cid)
            # An undetermined chunk is in neither set. It is not a leak (nothing says the
            # principal was excluded) and its absence is not under-retrieval (nothing says they
            # were entitled). The propagation axis reports it, as `unverifiable`.
            was_undetermined = frozenset(returned) & undetermined
            over = frozenset(returned) - truth - undetermined
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
                    absent_from_index=absent,
                    undetermined_returned=was_undetermined,
                )
            )
    return results, skipped


def verify(
    scenario: Scenario,
    variant: Variant,
    retrieve: Retrieve | None = None,
    enforcement_site: str = "simulated",
) -> VerificationReport:
    findings, untraceable = check_propagation(scenario, variant)
    probes, skipped = run_probes(scenario, variant, retrieve)
    return VerificationReport(
        chunks_examined=len(variant.chunks),
        chunks_untraceable=untraceable,
        propagation=tuple(findings),
        probes=tuple(probes),
        probes_skipped=tuple(skipped),
        # A skipped probe means a boundary was never exercised, and so does a probe whose chunks
        # are not all in the index; the report must say so (DEC-007).
        partial=bool(skipped) or any(p.absent_from_index for p in probes),
        enforcement_site=enforcement_site,
    )
