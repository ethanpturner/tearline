# narrowed-after-ingest

**What this measures.** Drift detection in both directions, and that a stale index is reported as
one defect rather than one finding.

**The setup.** Both documents had their ACLs changed on 2026-03-01. The index was built on
2026-02-01 and never rebuilt.

| Chunk | Source changed | Index still says | Effect on `p-globex-eng` |
|---|---|---|---|
| `c-0071` | narrowed to `acme` | `acme, globex` | keeps access it **lost** — over-retrieval |
| `c-0081` | broadened to `acme, globex` | `acme` | lacks access it **gained** — under-retrieval |

## Why both directions belong in one scenario

The same principal is simultaneously over-served and under-served by the same stale index, in the
same run. That is not a contrived pairing — it is what a re-indexing lapse looks like once any ACL
churn has happened in both directions, which is the normal state of an organisation.

It also defeats two plausible tool designs at once. One that reports only leaks sees half of this
run. One that pools over- and under-retrieval into a single score reports it as net-zero.

`c-0071` is the documented enterprise oversharing pattern in miniature: nothing was breached, no
credential was stolen, no filter failed. A permission was tightened and the index did not hear about
it. The retrieval layer then enforced, faithfully, a grant that no longer exists.

## Why cause matters as much as verdict

`acl_modified_at` is later than `ingested_at`, so the index once matched its source. The ingestion
pipeline is not implicated — this is a cadence problem, and the fix is a re-index rather than a code
change (DEC-006).

Reporting it as a propagation fault would send someone to audit a pipeline that is working. The
distinction costs two timestamps and decides which team gets paged.

## The negative set

`drifted/expected-clean.yaml` forbids three conclusions, and the third is the one I would most
expect a tool to get wrong: that the `c-0081` finding is lower priority than the `c-0071` finding.
They are one defect with two symptoms. Ranking them invites fixing the leak and leaving the
staleness — which leaves the leak's cause in place.

It also forbids blaming the source document, which is correct and current, and blaming the
principal, whose grants are correct. The index is serving a permission that no longer exists, and
that is not a fact about the identity.

## Pass condition

Two findings, both `contradicted` with cause `drift`; over-retrieval of `c-0071` and under-retrieval
of `c-0081` for `p-globex-eng` in the same probe; clean for `p-acme-eng`; nothing from the negative
set. The clean variant, rebuilt after the ACL change, yields nothing.
