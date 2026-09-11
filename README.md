# tearline

**Status: runs against fixtures and against real stores.** `tearline` checks propagation, drift,
and differential retrieval across eight scenarios and sixteen variants offline. `tearline scan`
runs the same three axes against a live system: document ACLs from a POSIX filesystem, and the
index inventory and retrieval results from PostgreSQL + `pgvector` with row-level security
(DEC-017) or from Qdrant (DEC-018). Both adapters are exercised in CI against service containers.

It has not been pointed at a production-scale corpus, or at any store but those two. The
false-positive figure `tearline evaluate` prints is measured over **74 negative-set subjects** —
every chunk the truth sets do not name as a fault, and every probe row they mark clean — and stands
at zero. That set is derived rather than authored (DEC-023), so it grows with the corpus instead of
with the documentation.

The two are chosen for contrast rather than popularity, and they fail in opposite directions.
Postgres enforces in the engine, so an application that forgets its filter still cannot cross the
boundary and the residual risk is *completeness*. Qdrant filters on the payload value it is handed,
so the boundary lives entirely in application code — `retrieve_unfiltered` demonstrates it by
returning another tenant's points from the same query with the clause omitted.

Ground truth comes from a real source system too: `sources.FilesystemSource` reads document ACLs
from POSIX ownership and mode bits, which makes drift observable with real timestamps — `chmod`
moves `st_ctime`, and that is the signal separating a stale index from a broken pipeline.

**Neither catches a propagation fault.** Both serve a mislabelled chunk faithfully and quickly to
the wrong tenant while every control behaves correctly, which is the case for this tool and is now
shown against real stores rather than argued from a fixture.

It has also been pointed at two real applications at the commit before and after a shipped
authorization fix ([docs/eval/real-targets.md](docs/eval/real-targets.md)). Against LibreChat's
`rag_api`, 8 of 8 probes over-retrieve before pull request #319 and none after; the post-fix index
carries 1 under-retrieval, introduced by the fix itself, which a leak-only reading scores as
perfectly secure. Against Open WebUI 0.8.12 and 0.9.0, the store returns hits with no access
check at both versions and the fix for CVE-2026-44560 lives in the application, which is
DEC-018 observed on a real advisory. Those runs are live and not replayable in CI.

```
uv run tearline verify benchmarks/untagged-chunk --variant faulted-naive
uv run tearline evaluate     # every registered variant, scored against its expectations
uv run tearline scan path/to/target      # a real source system and a real index; reads only
```

A scan target is a directory holding `target.yaml` — naming the source root, its group-to-tenant
mapping, and the backend — beside a `shared/` directory holding the entitlement rule, the
principals to run as, and the probes. Nothing in it is optional: a missing entitlement rule is an
error rather than a default (DEC-012), and so is a missing group mapping (DEC-020), because a
guessed one is wrong in a way that surfaces as confident findings about the index.

## What it does

`tearline` verifies that a retrieval system's access control is real: that every chunk
in an index carries the entitlement its source document actually has, that those entitlements have
not drifted since ingestion, and that retrieval under one identity never returns content only
another identity may see.

A tearline, in an intelligence document, is the line below which the content is releasable to a
wider audience. The name is the unit of work: the tool is designed to check that the line in the
index is where the source system says it should be.

## What it is, in one line

Index-layer reconciliation — every chunk's tag compared against the source system's ACL, with drift
separated from a propagation fault — plus differential retrieval, the same probe under two
identities, scored for what was disclosed and for what was withheld.

## Why this does not already exist

OWASP's RAG Security Cheat Sheet prescribes three controls: store access-control metadata
(classification, owner, permitted roles, permitted tenants) alongside every vector chunk;
cryptographically sign source attribution; and perform regular cross-tenant testing to verify zero
cross-boundary retrieval. It names no tool for any of them.

The surrounding ecosystem does not fill the gap. Vector databases enforce the tenant filter they are
handed and never ask whether the tag is true. Authorization engines answer *is this principal
allowed to call this tool* — a question the application must remember to ask, and one whose honest
answer during a confused-deputy retrieval is yes. Red-teaming harnesses drive adversarial text at a
chat endpoint and never touch the index. Evaluation frameworks score whether retrieved text was
*relevant*, never whether it was *permitted*.

The one widely-cited real-world instance is the Microsoft 365 Copilot oversharing pattern, and the
framing that stuck is that Copilot did not overshare the data — the permissions did. The vendor
response is containment: stop indexing the risky material until it is cleaned up. There is no
verifier.

### Adjacent work

Three kinds of tool sit next to this one and none of them does what it does. Authorization engines
generate the filter a retrieval query carries — Oso compiles Polar to SQLAlchemy predicates over
pgvector, Permit.io and Cerbos translate a policy into a store filter, SpiceDB's guidance covers
pre- and post-filtering, Pangea attaches policies at ingestion. Each enforces; none asks whether the
tag it filters on is true. Sync ledgers record that a permission sync ran — Onyx's v4.0.0 admin
tooling shows each sync attempt and what failed, Elastic's connectors run an access-control sync
beside the content sync — and a ledger of attempts is not a comparison of the result against the
source. Knostic simulates queries across user profiles against Copilot and Glean and reports
oversharing at the answer layer; it is closed, it does not read the index, and it does not measure
under-retrieval. Its own account of Copilot after a permission is revoked — the file is gone from
the user's view and Copilot can still see it — is the drift class this tool's second axis exists
for ([knostic.ai](https://www.knostic.ai/blog/file-permissions-copilot)). On the measurement side,
ARBITER ([arXiv 2512.20535](https://arxiv.org/html/2512.20535)) scores an LLM-based access filter
for both false-allow and false-block, which is the only prior work found that counts
over-restriction as an error; it scores the filter, not a deployed index.

## The two failures it is designed to measure

**Over-retrieval** is the obvious one: an identity receives a chunk it is not entitled to.

**Under-retrieval** is the one that gets missed. Where entitlement filtering is applied after an
approximate nearest-neighbour scan, a highly selective policy can return nothing while matching
content exists. Confidentiality holds and completeness silently breaks — and a generation step handed
no context does not error, it answers anyway. A tool that measures only leaks would call that
system perfectly secure.

Both are measured. So is the false-positive rate against legitimate retrieval, because a verifier
that flags ordinary access is one nobody keeps running.

## Scope

`docs/architecture/project-scope.md` for scope and non-goals, `docs/architecture/decision-log.md`
for what is decided and why, `docs/architecture/evaluation-plan.md` for how it is intended to be
measured.

## Lineage

The claimed-versus-verified distinction is inherited from Trace, where it is recorded as DEC-009: a
finding means evidence supports a weakness, a documentation gap means it could not be determined
whether a control exists, and collapsing the two is the failure that project exists to avoid.
`whence` applies it to model provenance. `tearline` applies it to retrieval entitlements: an
entitlement tag is a claim, and the source system's ACL is what it is a claim about.
