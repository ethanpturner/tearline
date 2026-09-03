# Decision log

**Document version:** 0.1
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

**Note on lineage.** This is the third *declaration* of the vocabulary — `whence`'s data model,
`whence`'s pin verifier, and this data model — but only the pin verifier is code. Counted
accurately: **declared three times, implemented once.**

**Settled 2026-09-03: no extraction.** `attestrun` owns the definition for its own output and the
siblings keep theirs. A reader cloning this repository to see how retrieval entitlements are
verified should not need a second one to run it; four projects independently declaring the same
three verdicts is what demonstrates the distinction generalises; and a dependency from the verified
to the verifier points the wrong way. Recorded in `attestrun`'s DEC-001.

**Corrected 2026-09-03.** An earlier version of this entry called it the third hand-written
implementation and said extraction into `attestrun` was due. That overstated the duplication by
counting design documents as implementations, and the conclusion followed from the overstatement.
Two data-model tables agreeing on three words is not duplication worth factoring out; it is a shared
vocabulary, which is what a portfolio thesis is supposed to look like. Extraction becomes due when
the vocabulary is implemented, with behaviour, in two places — and neither project has product code
yet.

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

---

## DEC-011 — A fixture declares which chunks a query matches; relevance is given data

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** A probe in a fixture declares `matches` — the set of chunk identifiers a relevance
search returns before any entitlement filtering — as authored data. The fixture contains no chunk
text and the tool derives no relevance judgment of its own.

**Why.** Two reasons that point the same way.

Relevance is not what this tool tests. Whether retrieval surfaced the *useful* chunk is the question
RAGAS, TruLens and DeepEval already answer; the question here is whether it surfaced a *permitted*
one. Deriving relevance would mean reimplementing something well covered, badly, and then depending
on it for results about something else.

And deriving it would require chunk text in the fixture, which DEC-002 forbids. Since the tool never
reads content anywhere else, a fixture format that required it would be the one place the rule broke,
and it would break in the artefacts most likely to be copied into a repository and shared.

Taking `matches` as given also makes the tool's boundary explicit: everything upstream of it is the
retrieval system's business, and everything downstream is the entitlement question.

**Alternatives considered.** Embedding vectors instead of text, so relevance could be computed
without content. Rejected: an embedding is recoverable to an approximation of its source text, so it
is content with extra steps, and it would tie fixtures to a specific embedding model.

**Tradeoffs.** A fixture cannot catch a retrieval system whose relevance behaviour changes under
filtering — which is a real phenomenon and is exactly the mechanism behind DEC-008's under-retrieval
case. That case is therefore modelled by authoring the truncated result rather than by observing it,
and any claim about it is a claim about the model, not a measurement of a live system. Stated in the
evaluation plan.

---

## DEC-012 — The entitlement rule is supplied by the fixture, not built into the tool

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** Each source system's fixture states how tenant, roles, and direct grants combine into
an entitlement decision. The tool evaluates the stated rule; it has no default predicate.

**Why.** Systems genuinely differ. Roles may be additive or required-intersection; they may be
scoped within a tenant or granted globally; a direct principal grant may override a role denial or
be unioned with it; a document shared with two tenants may mean either tenant or only their
intersection.

A tool with one hardcoded predicate is correct for the system its author had in mind and quietly
wrong for the rest — and its wrongness does not surface as an error. It surfaces as *findings*:
confident reports that the index disagrees with the source system, generated by the tool
misunderstanding what the source system meant. That is worse than no tool, because the output looks
like exactly what the operator asked for.

**Alternatives considered.** A built-in default with per-system overrides. Rejected: the default
would be used unexamined, which is the failure above with an extra step. Requiring the rule to be
stated makes the assumption visible at the point where someone can check it.

**Tradeoffs.** Onboarding a new source system requires articulating its permission semantics before
any verification can run. That is real friction, and it is also the most valuable part of the
exercise — an organisation that cannot state its own entitlement rule has learned something before
the tool has emitted a single finding.

---

## DEC-013 — A fixture variant declares its enforcement model from a closed set

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** Each variant of a scenario declares a `filter` naming how the system under test
enforces entitlements. The set is closed, implemented in `scripts/validate_fixtures.py`, and grown
by decision-log entry. The initial members are `rule` (enforcement matching the source system's
stated entitlement rule) and `naive-tenant-exclusion` (absence read as no restriction).

**Why.** Faults live in two places and the fixture format only expressed one. In
`wrong-tenant-tag` the fault is in the data, so "what the system returns" and "the stated rule
applied to the index" are the same computation. In `untagged-chunk` they are not: the data is
identically wrong in two variants, and enforcement decides whether that is a latent defect or a
cross-tenant disclosure.

Conflating them would make a whole class of failure inexpressible — every enforcement bug, which is
where the OWASP guidance and the documented enterprise oversharing cases actually concentrate.

**Why the set is closed.** A fixture that could describe enforcement in free form could prove
anything, because the author would be writing both the bug and the expectation. Restricting to
implemented, named models means a scenario asserts *this specific, previously described enforcement
behaviour produces this outcome*, and adding a model requires arguing that a real system behaves
that way. This is the same treatment DEC-010 gives backends and for the same reason.

**Alternatives considered.** Letting a variant author the observed visibility outright, with no
model. Rejected: the checker could then no longer verify the scenario's own arithmetic, which is
the thing that has already caught authoring errors, and a scenario would become unfalsifiable
assertion.

**Tradeoffs.** A real system whose enforcement matches no implemented model cannot be represented
until a model is added. That friction is intended: it forces the behaviour to be described before it
is depended on.

---

## DEC-014 — A chunk records all of its source documents

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** `Chunk.source_document_ids` is a collection. A chunk drawn from several documents
records all of them; one drawn from none records an empty collection and is untraceable.

**Why.** The field was singular and could not represent a chunk drawn from more than one document —
ordinary output for any pipeline that merges short sections, deduplicates near-identical passages,
or windows across a document boundary. Authoring `boundary-crossing-chunk` made it inexpressible.

A singular field also forces a lossy choice at ingestion: record one source and discard the rest,
which destroys exactly the information needed to compute what a merged chunk may disclose.

**Tradeoffs.** Every consumer must handle the multi-source case, and the interesting rules — the
safe bound in DEC-015 — only exist because of it. That is the cost of representing what pipelines
actually produce.

---

## DEC-015 — The safe bound, and when `unverifiable` is permitted

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** For a chunk drawn from several documents:

- A principal may see it only if entitled by **all** its sources. That intersection is the **safe
  bound**.
- A tag that **exceeds** the safe bound is `contradicted`. Determinable, and a finding.
- A tag that **satisfies** the safe bound is `unverifiable`, reported with its sources, their
  divergence, the bound, and an explicit statement of what is not being claimed.
- `unverifiable` is **not available** for a tag that exceeds the safe bound.

**Why.** Chunking creates objects the source system has never had an opinion about. Where a chunk's
sources disagree, the correct entitlement is a policy question the organisation must answer and the
source system has not recorded — it might reasonably be the intersection, the more permissive
parent, or a refusal to merge at all. A tool that picks one is inventing policy and reporting it as
a finding.

But indeterminacy about the right answer is not indeterminacy about every wrong one. A chunk
contains material from all of its sources, so serving it to a principal that any source excludes
discloses that source's material to them. That is determinable without settling the policy question.

**The last clause is the load-bearing one.** Without it, a tool could abstain whenever sources
diverge — including on a tag granting a tenant access to material no source grants it — and the
abstention would look principled. Tying abstention to the safe bound keeps `unverifiable` narrow
enough to be honest.

**Alternatives considered.** Defaulting to the intersection and reporting anything else as a fault.
Rejected: it is the safe policy and it is still a policy, and a tool that enforces an unstated one
will be wrong about organisations that chose differently — while reporting that wrongness as
findings, which DEC-012 rejects for the same reason.

**Open questions.** Whether a chunk whose sources agree should be reported at all when it has
several of them. Currently it is treated as an ordinary determinate case, since the sources produce
one answer, and nothing in the fixtures yet tests that.

---

## DEC-016 — Verdict and cause are separate axes, and the undetermined cause is renamed

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** `MismatchCause`'s value for "the cause could not be determined" is **`undetermined`**,
not `unverifiable`. A finding may carry `verdict: contradicted` with `cause: undetermined`, and that
combination is expected rather than contradictory.

**Why.** DEC-006 named the value `unverifiable`, which collides with the `Verdict` value of the same
name on a different axis. `verdict: contradicted, cause: unverifiable` reads as a self-contradiction
and invites the failure it was written to prevent: letting uncertainty about *why* a mismatch exists
swallow certainty about *whether* it exists.

The two axes answer different questions. The verdict answers *does the index agree with the source*
— determinable from the two values alone. The cause answers *how did they come apart* — determinable
only from timestamps. Losing one because the other is unavailable discards a real finding, and
discards it in the reassuring direction, since an `unverifiable` verdict reads as "nothing
established here."

Distinct names make the combination legible at a glance, which matters because it is the common case
against source systems that do not expose ACL modification times.

**Alternatives considered.** Keeping one word and relying on the field name for disambiguation.
Rejected: findings are read quickly and under pressure, and a reader who has to consult a schema to
tell which axis a word is on will eventually not bother.

**Tradeoffs.** Two words for a similar idea. Acceptable — they are similar ideas about different
things, which is exactly when distinct words earn their cost.

---

## DEC-017 — Backend: PostgreSQL with `pgvector` and row-level security

**Date:** 2026-09-03
**Status:** Accepted

**Trust model: the engine enforces.** A row-level security policy is evaluated by the database, so
an application that forgets its `WHERE` clause still cannot read another tenant's rows. The boundary
does not depend on the retrieval code being correct.

**Decision.** Supported as the first backend, specifically because it is the configuration where
the tool's job is *hardest to justify* — if the engine holds the boundary, what is left to verify?

**What is still verifiable, and it is most of the point.** Engine enforcement guarantees that the
policy is applied. It guarantees nothing about whether the policy expresses the source system's
ACL. Propagation faults and drift (DEC-006) live entirely in how a chunk's tenant column was
populated at ingestion, which RLS never inspects — it enforces the value faithfully, exactly as
`wrong-tenant-tag` describes.

**The failure mode this backend contributes.** With an approximate index, entitlement filtering is
applied *after* the ANN scan unless a supporting index lets the planner push it down. A highly
selective policy — a tenant entitled to a small fraction of rows — can therefore return fewer
matches than exist, or none, while matching rows are present.

**Confidentiality holds and completeness silently breaks**, which is precisely DEC-008's
under-retrieval, occurring natively rather than as a bug. It is the strongest available argument
that a leak-only verifier is insufficient: on this backend, the most likely defect discloses nothing
and is invisible to any tool measuring only over-retrieval.

**What the tool cannot verify here.** That the RLS policy itself matches organisational intent. The
tool compares the index against the source system; whether the source system reflects what the
organisation meant is a different audit (`project-scope.md` §7).

---

## DEC-018 — Backend: Qdrant, where isolation is application-supplied

**Date:** 2026-09-03
**Status:** Accepted

**Trust model: the application enforces.** Multi-tenancy is a payload field — conventionally
`tenant_id` — with a tenant index, or per-tenant sharding. The store filters on the value it is
given and has no notion of who is asking.

**Decision.** Supported as the second backend, chosen for contrast with DEC-017 rather than for
popularity. Verifying both means the tool cannot assume the engine is on the operator's side.

**The specific gap.** Qdrant's JWT support (RBAC, GA since v1.9) restricts *which collection* a key
may touch and whether it may write. It does not bind a tenant: nothing injects `tenant_id == <claim>`
into a query. Qdrant's own multi-tenancy guidance states that ensuring a caller sees only their own
tenant relies on the application layer, and
[qdrant#8015](https://github.com/qdrant/qdrant/issues/8015) — *"Automatic Tenant-ID Injection via
JWT Claims or Tenant-Specific API Keys"*, open since 2026-01-30 — is a request for the binding that
does not exist.

So a claim that "Qdrant enforces tenant isolation via JWT" is inaccurate as commonly stated, and the
documentation says so. The boundary lives entirely in code the store never sees.

**What that changes for verification.** Everything DEC-017 leaves to the engine is here in scope. A
query issued without the tenant filter returns cross-tenant results correctly and quickly, so
differential probing (DEC-007) carries the weight that RLS carries on Postgres — it is the only
thing establishing that the boundary is applied at all, rather than merely available.

**The one thing that gets better.** Qdrant's filterable HNSW keeps the filter inside the graph
traversal, which mitigates DEC-017's post-filter truncation architecturally rather than eliminating
it. So the two backends fail in opposite directions: the engine-enforced one is prone to
under-retrieval, and the application-enforced one to over-retrieval. Reporting per backend rather
than merged (`evaluation-plan.md` §5) is what keeps that visible — a merged score would hide the
difference an operator is choosing between.

**Not yet decided.** Whether a third backend is worth adding. Two are enough to prevent a
premature abstraction (DEC-010), and a third should be argued for by a trust model neither of these
covers rather than by market share.

---

## DEC-019 — Retrieval is a bounded candidate set, filtered afterwards

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** A fixture variant may declare `ann_limit`: the number of candidates the approximate
search returns before entitlement filtering is applied. Filtering operates on that bounded set,
never on the whole corpus. Truth — what a principal is entitled to — is computed over the probe's
full relevance set regardless, so a chunk lost to the limit registers as under-retrieval.

**Why.** DEC-008 asserts that under-retrieval is a finding, and until now the fixture format could
not produce one without a mistagged chunk. That was a gap: the mechanism DEC-008 describes is
ordering and truncation, not mislabelling. Post-filter truncation is a property of how a search is
executed, and modelling it needs the candidate bound to be expressible.

It also makes DEC-017's residual risk testable. On an engine-enforced backend, confidentiality is
held by the database and the realistic defect is exactly this: a selective policy returning fewer
matches than exist. Without `ann_limit` the only backend whose main failure mode the fixtures could
represent was the application-enforced one.

**What it does not model.** The reason a chunk ranks where it does. Ordering is authored, like
`matches` itself (DEC-011), so the fixture demonstrates that the tool detects truncation — not that
a given backend or embedding produces it at a given k. That distinction is stated in the evaluation
plan and belongs in any claim made from these results.

**Tradeoffs.** Another authored dial, and dials can be tuned until a scenario says what its author
wants. Mitigated the same way as DEC-013's filters: `ann_limit` is one integer with one meaning,
checked by `validate_fixtures.py`, rather than free-form control over the result set.

---

## DEC-020 — Source system: a POSIX filesystem

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** The first source-system adapter reads document ACLs from POSIX ownership and mode
bits, with a supplied group-to-tenant mapping. World-readable becomes the `everyone` **role**, not a
wildcard tenant. An unmapped group yields `unknown`, never an empty-but-stated entitlement.

**Why a filesystem.** Every axis compared against authored documents until now, so the tool had
never read an ACL from a real system, and the drift axis in particular had never seen a real
timestamp. A filesystem supplies both, is common enough to be worth supporting on its own merits --
a large share of retrieval corpora are built from files on a share -- and needs no credentials or
service to test, which keeps it in the default suite rather than behind a `live` marker.

**Why the mapping is supplied.** The same reason DEC-012 gives about entitlement rules. A mapping
guessed from group names would be quietly wrong for every organisation that names groups
differently, and its wrongness would surface as confident findings that the index disagrees with the
source — generated by the tool misunderstanding what the source meant.

**Why world-readable is a role.** `everyone` is a grant the source system makes. Recording it as a
wildcard tenant, or as an empty entitlement, would put it on the same footing as a document whose
permissions were never set — which is the collapse DEC-003 exists to prevent, arriving through the
adapter rather than the model.

**On `st_ctime`.** It is the closest thing POSIX offers to "when the ACL last changed" and it is not
that: a content edit moves it too, so it says less about permissions than its use here implies. The
adapter documents the approximation rather than presenting it as exact. Recorded anyway because
DEC-006 prefers an approximate timestamp to none — with none, every mismatch resolves
`undetermined`, and the distinction between a stale index and a broken pipeline is lost for every
document.

**Open questions.** Whether to read POSIX ACLs (`getfacl`) where present, which express far more
than owner-group-other and would make the mapping richer. It also introduces a second permission
model on the same filesystem, and which one governs when they disagree is exactly the multi-system
authority question DEC-005 already records as unresolved.

---

## DEC-021 — The stated entitlement rule is composed from a closed vocabulary

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** DEC-012 requires the fixture to state its source system's entitlement rule. That
statement takes the form of three named clauses — tenant, role, direct — and a named combinator,
each drawn from a closed set held in `entitlement_rule.py`. A clause outside the set is refused at
load, and a missing rule is an error rather than a default.

**Why a closed set rather than an expression.** The obvious reading of DEC-012 is that the fixture
supplies a predicate the tool evaluates — an expression language, or a callable. That fails for the
reason DEC-013 gives about enforcement models: a fixture able to describe entitlement freely can
describe anything, and its author writes both the bug and the expectation, so a passing scenario
demonstrates only that two authored artifacts agree.

It also fails on a second count that DEC-013 does not face. An expression evaluator running text
from a configuration file is an execution surface, in a tool whose whole subject is what a system
should and should not let a caller reach.

**Why this is not the hardcoded predicate DEC-012 rejects.** The clauses cover the variations
DEC-012 names as its reason: roles additive (`intersects`) or required-intersection (`subset`),
scoped or global; direct grants unioned (`tenant AND (role OR direct)`) or able to substitute for
tenancy (`(tenant OR direct) AND role`); an empty tenant set restricting (`member`) or releasing
(`member-or-unrestricted`). What the tool has is no *default* — the failure DEC-012 identifies is a
predicate applied to a system nobody checked it against, and a rule that will not load without
being stated cannot be that.

**Tradeoffs.** A system whose semantics the vocabulary cannot express cannot be onboarded without
extending it. That is deliberate and it is visible: extending the set is a change to this
repository, reviewed, rather than a line in somebody's fixture. The set is expected to grow, and
each addition should name the real system that motivated it.

---

## DEC-022 — A returned chunk whose entitlement is undetermined is not over-retrieval

**Date:** 2026-09-03
**Status:** Accepted

**Decision.** When a probe returns a chunk that no source document backs — an untraceable chunk, or
an identifier the index inventory does not contain — the result records it in
`ProbeResult.undetermined_returned` and in neither `over_retrieved` nor `under_retrieved`. The
probe's verdict is unaffected by it.

**Why.** `over_retrieved` carries `verdict: contradicted`, which asserts the principal was not
entitled to what they received. For an untraceable chunk nothing establishes that. Nothing
establishes the opposite either — which is why the chunk is reported rather than ignored — but a
`contradicted` verdict on undetermined evidence is precisely the collapse DEC-003 exists to
prevent, arriving through the probe axis instead of through the model.

**This reverses what `orphaned-chunk` originally asserted,** and the reversal is recorded rather
than quietly applied. That truth set called the retrieval `over-retrieval` and attached a note
saying it was "not a claim that a disclosure occurred". The label and the note disagreed, and
DEC-016 already settled which of those a reader acts on: findings are read quickly and under
pressure, and a disclaimer in a `why:` field does not survive being pasted into a ticket. A tool
whose output needs a footnote to stop meaning the wrong thing has chosen the wrong output.

**What is still reported.** That the chunk exists, that it was served to the principal, and that
nothing available shows the retrieval was permitted. The propagation axis carries the
`unverifiable` verdict; the probe axis now records that the unverifiable chunk was served, on its
own axis rather than folded into the leak count. A run containing one marks the report `partial`
where the chunk was named by a probe and absent from the index.

**Tradeoffs.** An operator scanning only the leak count will not see it. Mitigated by printing the
undetermined rows above the summary and by `chunks_untraceable`, which DEC-003's reasoning already
requires to be reported alongside findings so that a low finding count cannot read as good news.

**Alternatives considered.** A fourth `ProbeOutcome` value. Rejected: outcome answers *how did the
returned set differ from truth*, and this is a statement that part of the returned set has no truth
to differ from. Putting it on the same enum would make `clean` mean two different things depending
on a field elsewhere.
