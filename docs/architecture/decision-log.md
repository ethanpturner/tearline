# Decision log

**Document version:** 0.1
**Status:** Proposed
**Last updated:** 2026-09-03

Every entry is Accepted or Rejected. Nothing is Proposed: an undecided question belongs in the
scope document or an issue, not here. Violating an accepted decision is a design change requiring a
new entry, not an implementation detail.

Numbering is local to this repository. Where a decision inherits reasoning from prior work, the
lineage is cited rather than the numbering continued.

---

## DEC-001 — A verdict is three-valued, never boolean

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** Every claim resolves to `verified`, `contradicted`, or `unverifiable`. No boolean
verdict, and no default that collapses the third value into either of the others.

**Why.** A chunk whose source document cannot be located has not been shown to be correctly
entitled, and it has not been shown to be wrongly entitled either. Reporting it as either is a
statement the evidence does not support. This is Trace's DEC-009 — a finding versus a documentation
gap — applied to entitlements rather than controls.

The failure it prevents is specific to this domain and worse than it first looks. A verifier that
reports "no leaks found" when it could not evaluate half the corpus produces exactly the false
assurance the tool exists to remove, and it produces it in the reassuring direction.

**Note on lineage.** This is the third hand-written implementation of this vocabulary: `whence`'s
domain model, `whence`'s pin verifier, and now here. Extraction into `attestrun` is due, and this is
intended to be the last local copy. Recorded so that a fourth is treated as a mistake rather than a
pattern.

---

## DEC-002 — Findings are reported by identifier; the tool does not read, store, or emit content

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** `tearline` operates on chunk identifiers, entitlement metadata, source-document
identifiers, and ACLs. It does not read chunk text, does not store it, and never emits it. A
cross-boundary retrieval is reported as *chunk `c-4471`, entitled to tenant B, returned to identity
A* — never by quoting what was returned.

**Why.** The tool's output is a report about a confidentiality failure, and that report is
circulated to people investigating it, pasted into tickets, and stored in CI logs. **A report that
quotes the leaked material is itself a leak**, and it is one that escapes the boundary the tool
exists to police, into systems with weaker controls than the index.

It is also unnecessary. Every question the tool asks — did this chunk carry the right entitlement,
did that entitlement drift, did this identity receive something it should not — is answerable from
identifiers and metadata. Content adds nothing to the finding and adds a great deal to the
consequence of mishandling it.

**Alternatives considered.** Emitting a redacted or truncated excerpt for context. Rejected: an
excerpt is still content, redaction of unstructured text is unreliable, and the identifier is
already sufficient for the reader to retrieve the chunk themselves under their own authorisation —
which is the correct place for that access decision to be made.

**Tradeoffs.** A reader cannot judge severity from the report alone. That is intended: severity of a
disclosure depends on what was disclosed, and deciding it requires looking at the content under
proper authority rather than having it forwarded to you by a scanner.

---

## DEC-003 — An absent entitlement is `unknown` and is never treated as permissive

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** A chunk with no entitlement metadata is recorded as `unknown`. It is never interpreted
as public, unrestricted, or inheriting a default. A retrieval that returns an `unknown` chunk is a
finding in its own right, not a pass.

**Why.** The permissive reading is the natural implementation and the dangerous one: a filter
written as "exclude chunks whose tenant differs from the caller's" admits every chunk that has no
tenant at all. Absence of a restriction is not a grant, and treating it as one converts an ingestion
bug into an access-control bypass.

This is the same rule Trace's DEC-009 states about missing documentation, and the direction of the
error is the same — silence read as a favourable answer.

---

## DEC-004 — The tool is read-only against every system it touches

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** No writes to the index, the corpus, the source system, or any ACL. Differential
retrieval is performed by issuing read queries under supplied identities. The tool does not create
test documents, does not provision identities, and does not modify a policy to observe the effect.

**Why.** A verifier that writes is a verifier that can cause the incident it is looking for. Seeding
a canary document into a live index to see who retrieves it means deliberately placing content and
hoping the boundary holds — and if it does not, the tool has performed the disclosure itself.

It also keeps the tool runnable against production by someone who is not authorised to change it,
which is the situation of most people who need the answer.

**Tradeoffs.** Some questions are only answerable by writing — whether a newly ingested document
gets the right tag, for instance. Those are answered against a fixture corpus, or not answered.

---

## DEC-005 — The source system's ACL is ground truth; the index's tag is a claim

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** Verification compares the index's entitlement metadata against the ACL held by the
system the document came from. Where the two disagree, the source system is authoritative and the
index is wrong. Where the source document cannot be located, the result is `unverifiable` rather
than a defence of either value.

**Why.** This is what makes the tool a verifier rather than a consistency checker. An index is
internally consistent when every chunk of a document carries the same tag, and that says nothing
about whether the tag is right. The claim lives in the index; the fact lives in the source system;
checking one against the other is the entire operation.

**Open questions.** Where several source systems disagree about the same document — a file synced
between two stores with different permission models — there is no obvious authority. Recorded as a
gap rather than resolved by picking one.

---

## DEC-006 — A propagation fault and a drifted ACL are distinct findings

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** A chunk whose entitlement never matched its source is reported separately from one
whose source ACL changed after ingestion. Both require the ingestion timestamp and the ACL's
last-modified time to distinguish; where either is unavailable, the finding is reported as
`entitlement-mismatch` with the cause `unverifiable`.

**Why.** They are different bugs with different fixes. A propagation fault means the ingestion
pipeline derives entitlements incorrectly and every future document is affected. Drift means the
pipeline is right and the index is stale, which is a re-indexing cadence problem. Collapsing them
tells an operator that something is wrong and nothing about which system to go and fix.

Merging them would also hide the more insidious one. Drift accumulates silently on a pipeline that
was correct on the day it was built, which is precisely the pattern behind the widely-documented
enterprise assistant oversharing cases.

---

## DEC-007 — Differential retrieval requires at least two identities

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** A differential probe compares what two or more distinct identities receive for the
same query. Where only one identity is available, the probe does not run and the result is
`unverifiable`. It is never reported as "no leak detected".

**Why.** A single identity's results cannot demonstrate isolation. Everything returned may be
legitimately its own, and the probe has established nothing about the boundary. Reporting that as a
pass is the strongest possible version of the false assurance DEC-001 exists to prevent, because it
is generated by a check that appears to have run successfully.

---

## DEC-008 — Under-retrieval is a finding, not a success

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** A differential probe scores two failures. **Over-retrieval**: an identity received a
chunk it is not entitled to. **Under-retrieval**: an identity did not receive a chunk it *is*
entitled to and which matched the query. Both are reported; neither is subordinate to the other.

**Why.** Where entitlement filtering is applied after an approximate nearest-neighbour search, a
selective policy can return nothing while matching content exists — the filter discards the
candidates the index found, and the index is never asked for more. Confidentiality holds;
completeness fails silently.

That failure is dangerous rather than merely annoying, because the generation step does not error
when handed no context. It answers anyway, from parametric memory, with no signal to the user that
retrieval returned nothing. A confident answer with no retrieved basis is a worse outcome than an
error, and a tool that measures only leaks would score the system that produces it as perfectly
secure.

**Tradeoffs.** Under-retrieval requires knowing what the identity *should* have received, which
means an authored entitlement map. It is therefore measurable against fixture corpora and only
partially against a production index, and the evaluation plan says so.

---

## DEC-009 — Truth sets are authored and never supplied to the tool

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** Every scenario separates the corpus and index the tool is given from the authored
entitlement map used to score it. Nothing under `expected/` is readable during a run, and the
negative set — legitimate retrieval that must not be flagged — is authored with the same care as
the positive set.

**Why.** A benchmark that hands the system its own answer key measures nothing. The negative set is
load-bearing here in particular: a verifier that flags every retrieval achieves perfect recall and
is useless, so the false-positive rate is a headline number rather than a footnote.

---

## DEC-010 — Backend support is added by decision, and each states that backend's trust model

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** Each supported store is added by its own decision-log entry recording where isolation
is enforced — in the engine, or in application code — and what that implies for what the tool can
verify. No generic backend abstraction is written ahead of the second backend.

**Why.** These systems are not interchangeable in the way an abstraction would imply. Where the
engine enforces the policy, an application that forgets its filter still cannot cross the boundary,
and the residual risk is completeness. Where the tag is application-supplied, the boundary is
entirely in code the index never sees, and a mislabelled chunk is served correctly and quickly to
the wrong caller.

A tool that flattened those into one interface would report the same verdict for two systems with
very different failure modes, and would quietly encourage the assumption that the engine is on the
operator's side. Recording the trust model per backend is what keeps the difference visible.
