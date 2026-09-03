# boundary-crossing-chunk

**What this measures.** That the tool abstains where the source system genuinely has no answer, and
that abstention is narrow enough to still catch the wrong answers.

**The setup.** `doc-005` is shared with `acme` and `globex`. `doc-006` is `acme` only. Chunk
`c-0051` is drawn from both. The source system assigns ACLs to *documents* and has never had an
opinion about an object made from several of them — chunking manufactured a question nobody
answered.

## Why this is the scenario that decides whether the tool is real

Every other scenario compares a tag against a stated ACL. Here there is no stated ACL to compare
against, and the temptation runs both ways.

Assert an answer and the tool is inventing policy: it would have to decide that a merged chunk
inherits the intersection, when an organisation might legitimately decide it inherits the more
permissive parent, or that merging across differing ACLs should be refused at ingestion. The source
system has not recorded that decision and the tool does not get to make it.

Abstain freely and `unverifiable` becomes a shrug — and the evaluation plan's third divergence
category, "genuine ambiguity", becomes a disposal route for anything inconvenient.

## What the tool can still determine

The resolution is that indeterminacy about the *right* answer is not indeterminacy about every
*wrong* one.

A chunk drawn from several documents contains material from all of them, so a principal may see it
only if entitled by all of them. That intersection is the **safe bound**: not necessarily the
correct entitlement, but a floor no correct entitlement can go below.

| Variant | `c-0051` tag | Relation to safe bound | Verdict |
|---|---|---|---|
| `clean/` | `acme` | equals it | **`unverifiable`** — reported, not a fault |
| `faulted/` | `acme, globex` | exceeds it | **`contradicted`** |

So the tool abstains on exactly one question — is this tag *correct* — and answers the one that
matters operationally: does it disclose anything no source permits.

`faulted/expected-propagation.yaml` carries a `forbidden_verdicts` block making this enforceable.
The sources diverge identically in both variants, so a tool that keys abstention on divergence alone
emits `unverifiable` in both — and its abstention on a real cross-tenant disclosure would look
principled. That is the failure the scenario is built to catch.

## What abstention still reports

`clean/` is the first non-empty `expected-unverifiable.yaml` in this repository, and `c-0051`
appears in the propagation findings even though nothing is wrong with it. A chunk whose entitlement
cannot be verified is not silently counted as fine: the report names the sources, their divergence,
the safe bound, and the fact that the tag satisfies it.

The finding also records `what_is_not_being_claimed`. Saying what an abstention does *not* cover is
what stops a reader from over-reading it, and it is cheaper to write now than to explain later.

## The negative sets carry unusual weight here

`clean/expected-clean.yaml` forbids reporting `c-0051` as under-retrieved for the globex principal.
That would require the tool to assert globex *should* see the chunk — the exact policy call it just
declined to make. Abstaining on a question and then implying an answer through a related finding is
the subtlest way to lose the discipline.

It also forbids widening suspicion to `c-0052`, a well-determined single-source neighbour. And the
faulted variant forbids *"the chunking pipeline is broken"* — the clean variant merges the same two
documents and is safe — and *"doc-005 and doc-006 have inconsistent ACLs"*, since two documents with
different audiences is ordinary and the inconsistency is manufactured downstream.

## What authoring this changed

**`source_document_id` could not represent it.** The field was singular, so a chunk with two sources
was inexpressible — and multi-source chunks are ordinary output for pipelines that merge, deduplicate,
or window across boundaries. Now `source_document_ids`, and the existing scenarios were migrated
(DEC-014).

**The safe-bound rule needed stating.** Recorded as DEC-015, along with the condition on when
`unverifiable` is permitted at all.

## Pass condition

**`clean/`:** `c-0051` reported `unverifiable` with `satisfies_safe_bound: true`; no over- or
under-retrieval for either principal; nothing from `expected-clean.yaml`.

**`faulted/`:** `c-0051` reported `contradicted` with cause `exceeds-safe-bound`; over-retrieval of
`c-0051` for `p-globex-eng`; **no `unverifiable` verdict anywhere**.
