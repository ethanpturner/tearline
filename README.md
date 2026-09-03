# tearline

**Status: runs against fixtures and against real stores.** `tearline` checks propagation, drift,
and differential retrieval across eight scenarios and sixteen variants offline. `tearline scan`
runs the same three axes against a live system: document ACLs from a POSIX filesystem, and the
index inventory and retrieval results from PostgreSQL + `pgvector` with row-level security
(DEC-017) or from Qdrant (DEC-018). Both adapters are exercised in CI against service containers.

It has not been pointed at a production-scale corpus, or at any store but those two. The
false-positive figure `tearline evaluate` prints is measured over three negative-set subjects,
which is what the corpus currently supports and is stated that way rather than as a rate.

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
