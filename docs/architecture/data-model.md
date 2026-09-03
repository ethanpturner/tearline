# Data model

**Document version:** 0.1
**Status:** Proposed
**Last updated:** 2026-09-03

Authoritative for field names, types, and enumerations. Code conforms to it; it does not describe
code. A conformance test is intended to parse the tables below and compare them to the
implementation in both directions.

Every object is immutable and forbids unknown fields. **No object in this model has a field that
holds chunk text** (DEC-002); that absence is a design property, not an omission.

## 1. Registry

| Object | Section | Status |
|---|---|---|
| `Principal` | 2 | NOT IMPLEMENTED |
| `Entitlement` | 3 | NOT IMPLEMENTED |
| `SourceDocument` | 4 | NOT IMPLEMENTED |
| `Chunk` | 5 | NOT IMPLEMENTED |
| `PropagationFinding` | 6 | NOT IMPLEMENTED |
| `Probe` | 7 | NOT IMPLEMENTED |
| `ProbeResult` | 8 | NOT IMPLEMENTED |
| `VerificationReport` | 9 | NOT IMPLEMENTED |

## 2. `Principal`

An identity retrieval is performed as. Supplied by the caller; never provisioned by the tool
(DEC-004).

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | str | yes | Stable identifier in the source system's terms. |
| `label` | str | yes | Human-readable, for reports. Not an identifier. |
| `tenant` | str \| None | no | `None` means the principal is not tenant-scoped, not that it spans all tenants. |

## 3. `Entitlement`

What a document or chunk requires of a reader.

| Field | Type | Required | Notes |
|---|---|---|---|
| `state` | `EntitlementState` | yes | See section 10. |
| `tenants` | frozenset[str] | yes | May be empty. Empty is not "all". |
| `roles` | frozenset[str] | yes | May be empty. |
| `principals` | frozenset[str] | yes | Direct grants, if the source system expresses them. |
| `classification` | str \| None | no | Open vocabulary, normalized. |

## 4. `SourceDocument`

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | str | yes | |
| `system` | str | yes | Which source system asserted the ACL (DEC-005). |
| `entitlement` | `Entitlement` | yes | Ground truth. |
| `acl_modified_at` | datetime \| None | no | `None` makes drift `unverifiable`, never absent (DEC-006). |

## 5. `Chunk`

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | str | yes | Index-assigned. |
| `source_document_ids` | tuple[str, ...] | yes | All documents the chunk draws on (DEC-014). Empty means untraceable — `unverifiable`, never a pass. More than one triggers the safe-bound rule (DEC-015). |
| `entitlement` | `Entitlement` | yes | The claim held in the index. |
| `ingested_at` | datetime \| None | no | `None` makes drift `unverifiable` (DEC-006). |

## 6. `PropagationFinding`

| Field | Type | Required | Notes |
|---|---|---|---|
| `chunk_id` | str | yes | |
| `verdict` | `Verdict` | yes | |
| `cause` | `MismatchCause` | yes | See section 10. Distinguishes a propagation fault from drift. |
| `expected` | `Entitlement` \| None | no | From the source document. `None` when the document was not located. |
| `observed` | `Entitlement` | yes | From the index. |

## 7. `Probe`

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | str | yes | |
| `query` | str | yes | Authored probe text. Never derived from corpus content. |
| `principals` | tuple[str, ...] | yes | At least two, or the probe does not run (DEC-007). |
| `expected_visible` | frozenset[str] | yes | Chunk ids each principal should receive. Authored; scenario-side only. |

## 8. `ProbeResult`

| Field | Type | Required | Notes |
|---|---|---|---|
| `probe_id` | str | yes | |
| `principal_id` | str | yes | |
| `returned` | tuple[str, ...] | yes | Chunk **ids**. Never content (DEC-002). |
| `over_retrieved` | frozenset[str] | yes | Returned and not entitled. |
| `under_retrieved` | frozenset[str] | yes | Entitled, matched, and not returned (DEC-008). |
| `verdict` | `Verdict` | yes | |

## 9. `VerificationReport`

| Field | Type | Required | Notes |
|---|---|---|---|
| `chunks_examined` | int | yes | |
| `chunks_untraceable` | int | yes | Chunks with no locatable source document. |
| `propagation` | tuple[`PropagationFinding`, ...] | yes | |
| `probes` | tuple[`ProbeResult`, ...] | yes | |
| `probes_skipped` | tuple[str, ...] | yes | Probe ids not run, with a reason — fewer than two principals, or a transient failure. |
| `partial` | bool | yes | True when anything was skipped. A partial run's silence is not a pass. |

## 10. Enumerations

**`Verdict`** — closed. `verified`, `contradicted`, `unverifiable` (DEC-001).

**`EntitlementState`** — closed. `stated`, `unknown`. A chunk carrying no entitlement metadata is
`unknown`; there is no `public` or `unrestricted` value, because the model must not offer a way to
record absence as a grant (DEC-003). A genuinely public document is `stated` with the source
system's own public marker in `roles`.

**`MismatchCause`** — closed. `propagation-fault` (never matched), `drift` (source ACL changed after
ingestion), `undetermined` (timestamps unavailable to distinguish the two) (DEC-006, renamed by
DEC-016),
`indeterminate-source` (sources diverge and the tag satisfies the safe bound),
`exceeds-safe-bound` (sources diverge and the tag grants beyond what all of them permit) (DEC-015).

**`ProbeOutcome`** — closed. `clean`, `over-retrieval`, `under-retrieval`, `both`, `not-run`.

## 11. Rules that are not fields

- **No field holds chunk text, and none may be added** (DEC-002). A finding names identifiers.
- **An empty `tenants` set is not "all tenants".** Where a system genuinely grants everyone, that is
  recorded as a stated role, not as an absence.
- **A chunk with no source documents is `unverifiable`.** It is never counted as clean, and
  `chunks_untraceable` is reported alongside the findings so that a low finding count cannot be read
  as good news without also reading how much was checkable.
- **A multi-source chunk is entitled to a principal only if all of its sources are** (DEC-015). The
  intersection is the safe bound; a tag exceeding it is `contradicted`, and `unverifiable` is
  unavailable in that case.
- **A verdict and a cause are independent** (DEC-016). `verdict: contradicted` with
  `cause: undetermined` is the expected shape wherever a source system exposes no ACL modification
  time, and an unknown cause never downgrades a determinable verdict.
- **A skipped probe never contributes a passing result** (DEC-007). `probes_skipped` and `partial`
  exist so that skipping is visible in the report rather than only in logs.
