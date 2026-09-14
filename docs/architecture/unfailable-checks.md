# Checks that cannot come out false

**Audited:** 2026-09-14, as part of a sweep across all five sibling repositories. Detector at
`docket`'s `scripts/audit_unfailable.py`, run against this tree; the taxonomy and the reasoning
behind the sweep are on that repository's page of the same name.

Development here is parked (DEC-025), so this page records rather than changes. One finding is
confirmed and it does not affect a measurement.

## The taxonomy

| | What it looks like |
|---|---|
| **A** | A filter naming a value nothing assigns. |
| **B** | A metric whose numerator or denominator cannot vary, usually because its input is authored rather than captured. |
| **C** | A guard whose failure branch is unreachable, most often because a fallback always satisfies it. |
| **D** | A claim true of one path and silent about the others, with no test that would fail if the enforcement were removed. |
| **E** | A polarity disagreement: a question, a label and the field it is stored in pointing in different directions. |
| **F** | A test that cannot fail. |

## Confirmed

### A — `ProbeOutcome.NOT_RUN` is a state no probe result can carry

`src/tearline/domain.py:59` declares `NOT_RUN = "not-run"` on `ProbeOutcome`. Nothing assigns it.
`verify.run_probes` builds an outcome from four cases only — `BOTH`, `OVER_RETRIEVAL`,
`UNDER_RETRIEVAL`, `CLEAN` — and a probe that cannot run never produces a `ProbeResult` at all: it
is appended to a separate `skipped` list and surfaces as `VerificationReport.probes_skipped`
(DEC-007, fewer than two identities means nothing about the boundary was exercised).

So the mechanism exists and works. What does not exist is the enum member that appears to
represent it. The text a reader sees, `not-run`, is printed by `__init__.py` from
`probes_skipped`, not from an outcome.

**The consequence is a schema claim the code cannot honour.** `ProbeOutcome` is a field on a
domain object that `--json` serialises, so a consumer reading the emitted document — or generating
a type from it — will handle a `"not-run"` outcome that never arrives, and will not learn from the
enum that skipped probes live in a different field entirely.

**Not changed.** Removing a member from a serialised vocabulary is a schema change, and this
repository is parked: the corpus replays, the measurements stand, and behaviour does not move
without a named adopter (DEC-025). The one-line fix is to delete the member; the reason to prefer
recording it is that nothing reads the schema today, and a parked project that starts making small
schema changes is a project that is not parked.

## Cleared

| Candidate | Why it is not a finding |
|---|---|
| **D — "the adapters contain no write path"** | `tests/unit/test_backends.py::test_a_shipped_adapter_contains_no_write` walks the AST of every shipped module and refuses string-constant write heads, f-string write heads, `execute()` of a computed statement, and non-read `_request` verbs. It was mutation-proved on 2026-09-10 against three planted shapes, one of which — the f-string head — it had previously passed. The enforcement is structural and the test fails if it is removed. |
| **B — "0 false positives over 74 negative-set subjects"** | Mutation-verified, and the verification is published beside the figure (DEC-023): flagging every multi-tenant chunk as exceeding its safe bound fires the check, and a spurious under-retrieval on clean probe rows fires 31 of the 74. A rate that can be driven off zero by a planted error is a rate that could have been non-zero. |
| **B — the paired-study and real-target figures** | Captured live against local stores on 2026-09-10 and stated as such at the top of both pages, including the fact that neither replays in CI. The truth set was authored before any model reviewer ran (DEC-009), and the authoring order is recorded in `paired-study/matrix.yaml`'s own header. |
| **A — `Verdict.CONTRADICTED`** | Reachable and reached: `run_probes` assigns it whenever a probe over- or under-retrieves, and the real-target measurement records 8 of 8 probes contradicted before a fix and 1 of 8 after. |
| **A — `MismatchCause.UNDETERMINED`** | Assigned wherever a source system exposes no ACL modification time, which DEC-016 names as the expected shape rather than an edge case. |
| **A — `EntitlementState.UNKNOWN`** | Assigned by `Entitlement.intersect` and exercised by the `boundary-crossing-chunk` scenario. |
| **F — the unit tests** | The detector found no test whose assertions compare only literals, and none without an assertion or a `raises`. |

## Not applicable here

**E, polarity.** This repository's verdicts are reported in one direction throughout: a
`ProbeResult` names what was over-retrieved and what was under-retrieved as separate sets, rather
than a single boolean whose sense has to be remembered. The failure that produced `docket`'s worst
defect — a question asked in one direction and recorded in the other — has no analogue here,
because nothing asks a question whose answer is stored under a label that negates it.
