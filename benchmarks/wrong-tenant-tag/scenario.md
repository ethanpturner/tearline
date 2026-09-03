# wrong-tenant-tag

**What this measures.** The basic propagation fault, and the fact that a single mislabelled chunk
produces two different failures in two different principals.

**The fault.** Chunk `c-0022` comes from `doc-002`, a `globex` document. The index labels it `acme`.
Every other field in `faulted/index.yaml` is identical to `clean/index.yaml`, so a diff between the
two files is exactly the fault and nothing else.

## Why one fault, two findings

| Principal | What happens | Finding |
|---|---|---|
| `p-acme-eng` | receives `c-0022` | **over-retrieval** — another tenant's content |
| `p-globex-eng` | no longer receives `c-0022` | **under-retrieval** — its own content withheld |

The second row is the point of the scenario. A tool that hunts for leaks finds the first and reports
the second as healthy — so the tenant whose data was withheld sees no finding, and the answer their
system produces is quietly built on less than it should have been. Nothing errors. The result set is
not even empty (DEC-008).

Note also what did *not* go wrong: the retrieval layer behaved correctly throughout. It enforced the
tag it was given, promptly and precisely. The tag was wrong. That is the failure this whole project
is about, and it is invisible to anything that tests the retrieval layer's behaviour rather than its
inputs.

## Why it is a propagation fault and not drift

`doc-002`'s `acl_modified_at` is 2026-01-11; `c-0022`'s `ingested_at` is 2026-02-01. The ACL has not
moved since ingestion, so the index never matched the source. That makes it a pipeline bug affecting
every future document rather than a re-indexing cadence problem, and the two need different people
to fix them (DEC-006).

`narrowed-after-ingest` is the same shape with the timestamps reversed, and
`narrowed-without-timestamps` is the case where they are unavailable and the cause must resolve
`unverifiable` rather than be guessed.

## The negative sets

`clean/` is the same corpus with the fault removed, and the tool must find nothing in it. A scenario
without its clean twin measures recall and says nothing about false positives.

`expected-clean.yaml` names the legitimate patterns most likely to be flagged by a naive
implementation: a document shared across two tenants (the commonest shape in any shared corpus), a
principal holding more roles than a chunk requires, and correct exclusions. The faulted variant adds
two more — the sibling chunk from the same document must not be flagged, and the unrelated probe
must not be degraded once a fault is found.

It also names two conclusions the tool must not reach: that `doc-002` is misconfigured, which sends
an operator to fix the one thing that is correct; and that `p-acme-eng` is over-privileged, which
gets an identity narrowed for no reason. An entitlement tool that reports identities rather than
data will do real damage in an organisation.

## What authoring this changed

Two things the design documents had not settled, both found by trying to write the fixture rather
than by reading the plan.

**Relevance has to be given data.** A probe needs to know which chunks a search would return before
filtering. Deriving that requires chunk text, which DEC-002 forbids the fixture from containing —
and relevance is not what this tool tests anyway. So `probes.yaml` declares `matches` directly.
Recorded as DEC-011.

**The entitlement rule has to come from the fixture.** Computing who should see what needs a rule
combining tenant, roles, and direct grants, and systems combine them differently. A hardcoded
predicate would be quietly wrong against every system that does not share its assumption, and would
report that wrongness as findings about the index. Recorded as DEC-012, with the rule stated in
`shared/entitlement-rule.yaml`.

The scenario layout also changed: `shared/` plus `clean/` and `faulted/` rather than the flat layout
the evaluation plan originally specified. Keeping the two indexes as sibling files is what makes the
fault a one-line diff.

## Pass condition

**Faulted:** one propagation finding on `c-0022` with cause `propagation-fault`; over-retrieval of
`c-0022` for `p-acme-eng`; under-retrieval of `c-0022` for `p-globex-eng`; `pr-002` clean for all
three principals; nothing from `expected-clean.yaml`.

**Clean:** no findings of any kind, and no `unverifiable` anywhere — every chunk traces, every
timestamp is present, and every probe has two or more principals, so there is no instrument limit to
report.
