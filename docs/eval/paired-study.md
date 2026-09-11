# The paired study: code review beside index verification

*Truth set: `paired-study/matrix.yaml`, authored before any model reviewer runs (DEC-009).
Observed columns: `paired-study/observed.yaml`. Rules: `paired-study/semgrep-rules.yaml`.
Provenance: ragref scans live against local pgvector and Qdrant, captured 2026-09-10; rag_api
runs as recorded in [real-targets.md](real-targets.md); Semgrep OSS 1.177.0 offline the same day.
None of it replays in CI: the stores would have to be populated first, and the SARIF is held
outside the repository. `tests/unit/test_paired_study.py` holds the files and this page in
agreement on shape and on the counts quoted here.*

The question the study asks is who catches what. A code reviewer reads the code that derives
entitlement tags and applies filters. `tearline` reads what that code produced in a deployed index
and what the index returns to each principal. The two see different things, and the claim under
test is that the difference is measurable rather than argued.

The reviewer side is a panel. Semgrep with hand-written rules is the deterministic floor: it shows
what a pattern can express. Two model reviewers, Google's Mantis and OpenAI's Codex Security, are
the columns still to run; they are present in `observed.yaml` as `not-run` so the file's shape does
not change when they land.

## Targets

**ragref** ([ethanpturner/ragref](https://github.com/ethanpturner/ragref), `main` at af01df1) is a
reference application built as a verification target: a POSIX corpus of two tenants and fourteen
documents, chunked and written to pgvector under row-level security and to Qdrant with an
application-supplied filter, retrieved as a principal. Eight branches each inject one fault, one
commit off `main`. The truth for each was written before either tool ran and is reproduced in the
matrix verbatim.

**rag_api** (LibreChat, pgvector) at `4985b37`, the parent of pull request #319, which closed six
authorization holes on 2026-08-15. The rows below list them as seven because the listing route and
the three document routes are scored separately. The truth for these rows was written from the
pull request's description after `tearline` had run and before any model reviewer had; the matrix
says so.

## The matrix

| Row | Fault | Expected | tearline | Semgrep |
|---|---|---|---|---|
| ragref/f-parent-dir | tenant from directory name, not owning group | both | yes: propagation, differential | no |
| ragref/f-exclusion | exclusion-shaped tenant predicate | both | yes: propagation, differential on pgvector | yes |
| ragref/f-untagged | deep documents written with no entitlement | tearline | yes: propagation, under-retrieval | no |
| ragref/f-limit-first | ANN candidate bound below k, filter after scan | tearline | yes: under-retrieval on pgvector | partial |
| ragref/f-chmod | ACLs narrowed after ingest, no code change | tearline | yes: drift, differential | no |
| ragref/f-superuser | application connects as superuser | reviewer | refused: error, not a finding | yes |
| ragref/f-merge | chunk merged across a tenant boundary | tearline | yes: exceeds-safe-bound, differential | no |
| ragref/f-policy-intent | README intent the ACL and policy do not express | neither | no, by decision | no |
| rag_api/ids-listing | `GET /ids` lists every identifier | both | yes: 8 of 8 probes over-retrieve | yes |
| rag_api/query-multiple | `POST /query_multiple` unauthorized | both | yes: 8 of 8 probes over-retrieve | partial (v1 only) |
| rag_api/query-first-hit | `/query` authorized from the first hit | reviewer | not exercised | yes |
| rag_api/documents-by-any-id | document routes read or delete any id | reviewer | not exercised; delete is a write | yes |
| rag_api/null-owner | chunk with no owner reads as everyone's | both | yes: propagation, differential | yes |
| rag_api/rollback-by-file-id | rollback deletes with no owner predicate | reviewer | no: ingestion write | no |
| rag_api/shared-table-collection-id | lookups omit `collection_id` | reviewer | no: probes within one collection | no |

## Counts, with denominators

**tearline, ragref: 6 of 8 faults caught**, and the two it did not catch are the two the truth set
says it should not. On `f-superuser` the pgvector adapter raised `BypassesRowSecurity` and exited 1
having verified nothing, which is the DEC-017 refusal rather than a clean report; on
`f-policy-intent` the source ACL agrees with the index and there is no finding by decision
(evaluation plan section 7). Every catch matched the expected axis: five faults on the propagation
or drift axis with a differential delta beside them, `f-limit-first` on the differential axis
alone. On Qdrant, `f-exclusion` and `f-limit-first` reach the probes only as stored-data faults,
because the differential axis there runs the verifier's own filtered search (see the matrix
header and issue #5).

**tearline, rag_api: 8 of 8 probes over-retrieve pre-fix, 0 of 8 post-fix, and 1 of 8 probes
under-retrieves post-fix.** That last figure is the fix's own breaking change: a chunk with no
owner became readable by nobody, including its owner. The full table is on the real-targets page.

**Semgrep, ragref: 3 of 8 faults caught**, `f-exclusion`, `f-limit-first`, `f-superuser`, with
one false positive on every branch including `main`. The false positive is the generic rule for a
nearest-neighbour `ORDER BY ... LIMIT` with no tenant predicate in the statement: it cannot see
the row-level security policy that supplies the predicate, so it fires on the clean branch and
every fault branch alike. Of the three catches only two are generic; the `f-limit-first` rule
matches a literal `ef_search` value and was written knowing the fault. The default rulesets
(`p/default`, `p/python`, `p/security-audit`) produced five findings, the identical set on all
nine branches, touching 0 of 8 faults.

**Semgrep, rag_api: 4 of the 6 holes pull request #319 names, pre-fix**; in the seven-row listing
above, 4 yes, 1 v1-only, 2 no. Two rules are both generic and precise: `null-owner-admits-everyone`
(`if owner is None or owner == caller`) and `authorize-result-set-from-first-hit`. The route rule
is app-shaped, naming one library's store methods. The v1 rule set also caught `/query_multiple`
and produced sixteen false positives post-fix, because a pattern cannot see that a filter held in a
variable was built from the caller's scope; v2 exempts `filter=<variable>` and loses the hit. The
default rulesets produced thirty findings pre-fix and the same thirty post-fix, touching 0 of 6
holes.

## What the floor cannot express

Five of the eight ragref faults have no pattern, and the reasons are structural rather than a
matter of better rules.

- **f-chmod.** No code changed. Drift is a relation between two systems at two times, and a
  rule reads one file at one time.
- **f-untagged.** A depth condition in the ingester returns an unknown entitlement. Nothing leaks;
  the fault is a missing tag, visible only in the index.
- **f-merge.** A chunking heuristic folds a document tail onto the next head. The code names no
  tenant, so no tenant rule can fire.
- **f-parent-dir.** A directory name standing in for a group. Both are strings; a rule that flagged
  deriving a tenant from a path would flag every multi-tenant layout.
- **f-policy-intent.** The only change is a sentence in the README. Code agrees with code.

On rag_api the same shape recurs: a missing predicate on a shared table is not a pattern without
knowing which table is shared, and an ingestion-path write reaches no route a rule was pointed at.

## What is pending

The Mantis and Codex Security columns. Each will be scored against the same matrix, one run per
row in the first pass, five on the rows where the two disagree with each other or with the floor.
The rows to watch are `f-untagged`, `f-limit-first`, and `f-chmod`, where nothing leaks today and
a reviewer's validation stage is built to dismiss what does not: DEC-008's argument, that an empty
context produces a confident answer from parametric memory and a latent untagged chunk is a leak
one line away, is what those rows test.
