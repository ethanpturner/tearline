# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

`tearline` verifies that a retrieval index's entitlements match the source system's, and that
retrieval respects them.

**Verification runs against fixtures**: propagation, drift, and differential retrieval across eight
scenarios and sixteen variants, offline, scored against authored truth sets by `tearline evaluate`.

**It also runs against real systems.** `tearline scan` reads document ACLs from a POSIX filesystem
(DEC-020) and an index inventory and retrieval results from a backend — PostgreSQL with `pgvector`
and row-level security (DEC-017), or Qdrant (DEC-018). Both adapters are exercised in CI against
live service containers. What has *not* been done is a run against a production-scale corpus, or
against any store other than those two.

The entitlement rule is read from the target, never assumed (DEC-012, DEC-021), and the tool writes
nothing to either system — the adapters contain no write path at all, and
`tests/unit/test_backends.py` fails if one reappears (DEC-004).

Keep tense discipline: present indicative for what runs, "is designed to" for anything unbuilt. The
line that matters most is what a scan has and has not been pointed at.

## Read before changing anything

`docs/architecture/project-scope.md`, `docs/architecture/decision-log.md`,
`docs/architecture/data-model.md`, `docs/architecture/evaluation-plan.md`.

`data-model.md` is authoritative for field names, types, and enumerations.

## Binding constraints

Decided. Violating one is a design change requiring a new decision-log entry.

- **A verdict is three-valued** — `verified`, `contradicted`, `unverifiable` — never boolean
  (DEC-001). A chunk that could not be traced to a source document is `unverifiable`, never a pass.
- **Findings are reported by identifier; the tool never reads, stores, or emits chunk content**
  (DEC-002). A report that quotes leaked material is itself a leak, into systems with weaker
  controls than the index it came from. No field in the data model holds chunk text, and none may
  be added.
- **An absent entitlement is `unknown` and never permissive** (DEC-003). There is deliberately no
  `public` value in `EntitlementState`: the model must not offer a way to record absence as a grant.
- **The tool is read-only against every system it touches** (DEC-004). No writes, no canary
  documents, no provisioned identities, no policy changes to observe the effect.
- **The source system's ACL is ground truth; the index's tag is a claim** (DEC-005).
- **A propagation fault and a drifted ACL are distinct findings** (DEC-006). Where timestamps
  cannot distinguish them, the cause is `undetermined` — never guessed. The word is deliberately
  not `unverifiable` (DEC-016): that value lives on the *verdict* axis, and
  `verdict: contradicted, cause: undetermined` is a normal, expected combination.
- **A differential probe needs at least two identities** (DEC-007). With one, it does not run and
  the report says so. "No leak detected" from a single-identity probe is the forbidden output.
- **Under-retrieval is a finding** (DEC-008). A system that returns nothing is not a secure system,
  and the generation step does not error when handed no context.
- **Truth sets are authored and never supplied to the tool** (DEC-009). Every scenario has a clean
  twin; the false-positive rate is a headline number.
- **Backend support is added by decision, stating that backend's trust model** (DEC-010). No
  generic abstraction before the second backend.

## Working norms

- **The quality gate is `uv run ruff check . && uv run mypy && uv run pytest`**, plus
  `uv run tearline evaluate` and `uv run python scripts/validate_fixtures.py`.
- **The entitlement rule has exactly one implementation**, in `src/tearline/rules.py`. The fixture
  checker imports it. Two copies of the same predicate drift, and the drift surfaces as confident
  disagreement between the checker and the tool.
- **mypy is strict and covers `scripts/` too.**
- **Every domain object is immutable and forbids unknown fields.**
- **Where absence would read as a favourable answer, say so explicitly.** An empty tenant set is not
  "all tenants". A missing timestamp makes drift `unverifiable`, not absent.
- **Never put chunk content in a log record, a report, an error message, or a test fixture's
  expected output.** Reference chunks by id.
- **The default test run touches no real backend and needs no credential.** The `live` marker is
  deselected in `addopts` precisely so a bare `pytest` cannot reach one.
- **A scenario is registered in `benchmarks/scenarios.yaml` or it is not part of the set.**
- **Match the prose register** in docs and PR descriptions: flat declarative, no marketing
  language, no emoji, no second person. State the rule, then state why the alternative fails.

## Journal

`journal/YYYY-MM-DD-short-slug.md`, one file per session. Record the reasoning, not the diff.

## Relationship to sibling projects

One of three tools sharing a thesis: a security claim should be a checkable artifact rather than an
assertion. The others are [`whence`](https://github.com/ethanpturner/whence) (model provenance) and
[`attestrun`](https://github.com/ethanpturner/attestrun) (evaluation attestation).

The three-valued verdict is **declared** in both data models and **implemented** in exactly one
place, `whence/scripts/verify_pins.py`. **Settled: there is no extraction.** Each project declares its own; the agreement is documented
rather than imported, because a reader cloning this repository should not need a second one to run
it, and a dependency from the verified to the verifier points the wrong way. Do not build a commons
package, and do not treat the shared vocabulary as debt.

The claimed-versus-verified distinction is inherited from Trace's DEC-009. Cite that lineage where
it is load-bearing; do not continue another project's decision numbering here.
