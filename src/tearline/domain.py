"""Domain objects.

`docs/architecture/data-model.md` is authoritative. Every object is frozen and forbids unknown
fields.

**No object here has a field that holds chunk text, and none may be added** (DEC-002). That absence
is a design property: a report about a confidentiality failure gets pasted into tickets and CI logs,
which have weaker controls than the index it came from, so a report that quotes leaked material is
itself a leak.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Verdict(StrEnum):
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class EntitlementState(StrEnum):
    """There is deliberately no permissive value (DEC-003).

    A chunk carrying no entitlement metadata is `unknown`. The model offers no way to record
    absence as a grant, because the natural filter -- exclude chunks whose tenant differs from the
    caller's -- admits every chunk that has no tenant at all. A genuinely public document is
    `STATED` carrying the source system's own public marker.
    """

    STATED = "stated"
    UNKNOWN = "unknown"


class MismatchCause(StrEnum):
    """Independent of `Verdict` (DEC-016). `verdict: contradicted, cause: undetermined` is the
    expected shape wherever a source system exposes no ACL modification time."""

    PROPAGATION_FAULT = "propagation-fault"
    DRIFT = "drift"
    UNDETERMINED = "undetermined"
    INDETERMINATE_SOURCE = "indeterminate-source"
    EXCEEDS_SAFE_BOUND = "exceeds-safe-bound"


class ProbeOutcome(StrEnum):
    CLEAN = "clean"
    OVER_RETRIEVAL = "over-retrieval"
    UNDER_RETRIEVAL = "under-retrieval"
    BOTH = "both"
    NOT_RUN = "not-run"


class Principal(DomainModel):
    id: str
    label: str
    tenant: str | None = None
    roles: frozenset[str] = frozenset()


class Entitlement(DomainModel):
    state: EntitlementState
    tenants: frozenset[str] = frozenset()
    roles: frozenset[str] = frozenset()
    principals: frozenset[str] = frozenset()
    classification: str | None = None

    def intersect(self, other: Entitlement) -> Entitlement:
        """The safe bound for a chunk drawn from both (DEC-015)."""
        if EntitlementState.UNKNOWN in (self.state, other.state):
            return Entitlement(state=EntitlementState.UNKNOWN)
        return Entitlement(
            state=EntitlementState.STATED,
            tenants=self.tenants & other.tenants,
            roles=self.roles & other.roles
            if self.roles and other.roles
            else self.roles | other.roles,
            principals=self.principals & other.principals,
        )


class SourceDocument(DomainModel):
    id: str
    system: str
    entitlement: Entitlement
    label: str | None = None
    acl_modified_at: datetime | None = None


class Chunk(DomainModel):
    id: str
    source_document_ids: tuple[str, ...] = ()
    entitlement: Entitlement
    ingested_at: datetime | None = None


class PropagationFinding(DomainModel):
    chunk_id: str
    verdict: Verdict
    cause: MismatchCause
    observed: Entitlement
    expected: Entitlement | None = None
    detail: str = ""


class Probe(DomainModel):
    id: str
    query: str
    principals: tuple[str, ...]
    matches: tuple[str, ...]

    @property
    def runnable(self) -> bool:
        """Fewer than two identities cannot demonstrate isolation (DEC-007)."""
        return len(self.principals) >= 2


class ProbeResult(DomainModel):
    probe_id: str
    principal_id: str
    returned: tuple[str, ...]
    over_retrieved: frozenset[str]
    under_retrieved: frozenset[str]
    verdict: Verdict
    outcome: ProbeOutcome


class VerificationReport(DomainModel):
    chunks_examined: int
    chunks_untraceable: int
    propagation: tuple[PropagationFinding, ...]
    probes: tuple[ProbeResult, ...]
    probes_skipped: tuple[str, ...]
    partial: bool
