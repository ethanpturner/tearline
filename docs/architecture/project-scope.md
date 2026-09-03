# Project scope

**Document version:** 0.1
**Last updated:** 2026-09-03

## 1. Problem

A retrieval pipeline takes documents that have permissions, splits them into chunks that do not,
and stores the chunks in an index that enforces whatever tag it was handed. Three things can go
wrong between the source document and the answer, and nothing in the ecosystem checks any of them.

**Propagation.** The chunk's entitlement tag may not match its source document's ACL. Nothing
verifies the tag was derived correctly, and every vector store will enforce a wrong tag as
faithfully as a right one.

**Drift.** The source document's ACL may have changed after ingestion. The index holds a snapshot of
a permission that has since moved, and the retrieval layer has no idea.

**Enforcement.** Even with correct tags, retrieval may not respect them — or may over-respect them.
Where filtering is applied after an approximate nearest-neighbour scan, a selective policy can
silently return less than it should.

## 2. What `tearline` is designed to do

Given a source system's permission model and an index built from it, produce a verdict on each of
the three:

- **Propagation**: for each chunk, does its entitlement match its source document's ACL?
- **Drift**: has the source ACL changed since the chunk was ingested?
- **Differential retrieval**: does retrieval under identity A ever return chunks only B may see, and
  does it ever fail to return chunks A is entitled to?

Every answer is `verified`, `contradicted`, or `unverifiable`. A chunk whose source document cannot
be located is `unverifiable` — never "fine".

## 3. Non-goals

Out of scope by decision, not by deferral.

- **It does not enforce anything.** It is a verifier. OpenFGA, Oso, Cerbos and SpiceDB decide
  access; `tearline` is designed to check that the decision survived ingestion and retrieval.
- **It is not a guardrail or a runtime filter.** It does not sit in the request path, inspect
  prompts, or block responses.
- **It does not evaluate answer quality.** Relevance, groundedness and hallucination are covered by
  RAGAS, TruLens, DeepEval and others. The question here is whether retrieval was *permitted*, not
  whether it was *useful*.
- **It is not a poisoning or injection detector.** Adversarial content in the corpus is a different
  problem with different tools.
- **It never modifies the index, the corpus, or any ACL.** Read and probe only (DEC-004).
- **It does not read, store, or report document content** (DEC-002). It works in identifiers.
- **It is not a connector platform.** Backend support is added one at a time, by decision, and each
  addition states that backend's trust model.

## 4. Intended users

Someone who has built or inherited a retrieval system over permissioned documents and needs to
answer a question they currently cannot: *can any user retrieve something they should not, and would
we know?*

## 5. Success condition

On a corpus with authored entitlements, the tool detects introduced propagation faults, drifted
ACLs, and cross-identity leaks, while flagging legitimate retrieval at a low enough rate to be worth
running. Under-retrieval is measured alongside over-retrieval, because a system that returns nothing
is not a secure system.

A run that finds nothing and says why is a correct run.

## 6. Backends

Backend trust models differ enough that the choice is part of the design rather than an
implementation detail, and the first two are chosen for contrast:

- **PostgreSQL with `pgvector` and row-level security** — the one common configuration where the
  engine enforces the policy, so an application that forgets its filter still cannot read across the
  boundary. Its documented weakness is completeness, not confidentiality, which is precisely the
  under-retrieval case in §2.
- **A store where isolation is application-supplied** — the far more common shape, where the index
  enforces a tag it was given and the boundary lives entirely in application code.

Verifying both means the tool cannot assume the engine is on its side.
