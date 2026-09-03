# Evaluation plan

**Document version:** 0.1
**Status:** Proposed
**Last updated:** 2026-09-03

## 1. What is measured

Three axes, reported separately, plus a false-positive rate that applies across all of them.

| Axis | Question |
|---|---|
| Propagation | Does each chunk's entitlement match its source document's ACL? |
| Drift | Has a source ACL changed since ingestion, and is the change distinguishable from a propagation fault? |
| Differential retrieval | Does one identity receive what only another may see — and does it receive everything it should? |

The fourth number is the one that decides whether the tool is usable: **the rate at which
legitimate retrieval is flagged.** A verifier that reports everything achieves perfect recall and
nobody runs it twice. It is a headline figure, not an appendix.

## 2. The truth-set rule

**Nothing under a variant's `expected-*` files is supplied to the tool during a run** (DEC-009).
Scenario layout:

```
benchmarks/<slug>/
  shared/
    documents.yaml          source documents and the ACLs the source system reports (ground truth)
    principals.yaml         the identities probes run as
    probes.yaml             authored queries, their principals, and `matches` (DEC-011)
    entitlement-rule.yaml   how this source system combines tenant, roles and grants (DEC-012)
  clean/
    index.yaml              entitlements propagated correctly
    expected-propagation.yaml
    expected-visibility.yaml
    expected-clean.yaml
    expected-unverifiable.yaml
  faulted/
    index.yaml              identical but for one named fault
    expected-*.yaml         the same four files for the faulted variant
  scenario.md
```

**Revised 2026-09-03.** This layout replaces a flat `corpus/` + `index/` + `expected/` arrangement,
after authoring the first scenario. Keeping the two indexes as sibling files makes a planted fault a
one-line diff, which is both self-documenting and hard to get subtly wrong. `shared/` also gained
`entitlement-rule.yaml`, which the original layout had no place for.

`scripts/validate_fixtures.py` recomputes visibility from the fixture's own rule and compares it to
the authored `expected-visibility.yaml`. It tests the scenario rather than the tool, so that a
failing run means the tool is wrong rather than the answer key. Hand-authored set arithmetic is
wrong more often than anyone admits.

`expected-clean.yaml` and `expected-unverifiable.yaml` carry as much weight as the fault files.
The first scores false positives. The second scores honesty — untraceable chunks, missing
timestamps, single-principal probes — where a confident verdict is wrong even though nothing is
broken.

## 3. Planted faults

Scenarios are built by taking a correct corpus and index, then introducing a **named** fault. The
correct version is retained, so every scenario runs twice: once where the tool must find the fault,
once where it must find nothing.

Fault classes intended for the first scenarios:

| Fault | What it tests |
|---|---|
| Chunk tagged with the wrong tenant | Basic propagation |
| Chunk with no entitlement metadata at all | DEC-003 — must not be read as permissive |
| Source ACL narrowed after ingestion | Drift, distinguishable from a fault |
| Source ACL narrowed, no timestamps available | Drift that must resolve `unverifiable`, not be guessed |
| Chunk whose source document is absent | Untraceable — `unverifiable`, and counted |
| Correct tags, filter applied post-ANN | **Under-retrieval with no leak** (DEC-008) |
| Document split so one chunk crosses a boundary | Chunking that manufactures an entitlement question the source never answered |

The last one is the interesting case and the reason chunk-level verification is not the same as
document-level: a paragraph quoted from a restricted appendix inside an otherwise public document
has no single correct answer in the source system, and the tool should say so rather than pick.

## 4. Differential retrieval

Every probe runs under at least two principals (DEC-007) and is scored on both directions:

- **over-retrieval** — returned and not entitled
- **under-retrieval** — entitled, matched the query, and not returned

Reported per probe and per principal, never pooled into one number. Pooling would let a system with
many small leaks and good recall score the same as one with perfect isolation and broken
completeness.

The under-retrieval measurement needs an authored entitlement map to know what *should* have
returned, so it is fully measurable against fixture corpora and only partially against a production
index. That limit is stated in the output rather than papered over.

A second limit follows from DEC-011. Because a fixture declares `matches` as given data, it cannot
observe a retrieval system whose relevance behaviour changes under filtering — which is the very
mechanism that produces post-filter truncation. In a fixture that case is *modelled* by authoring
the truncated result, so a passing `post-filter-truncation` scenario shows the tool detects the
shape of the failure, not that a given backend exhibits it. Establishing the latter requires a live
run against that backend.

## 5. Backends

Each scenario runs against every supported backend, and results are reported per backend rather
than merged (DEC-010). The point of running the same fault against an engine-enforced store and an
application-enforced one is that some faults are unreachable on one and trivial on the other; a
merged number would hide exactly the difference an operator is choosing between.

## 6. Divergence handling

When a run disagrees with a truth set, classify before editing anything:

1. **Tool defect** — fix the tool.
2. **Truth-set defect** — fix the expectation, and record why in the scenario's notes.
3. **Genuine ambiguity** — the source system does not determine the answer. Moves to
   `expected-unverifiable.yaml`.

**A run's output is never an argument for changing an expectation.** Category 3 is not a disposal
route for inconvenient failures, and the chunk-crossing-a-boundary case above is the one most
likely to be abused that way.

## 7. Not measured

- Retrieval relevance or answer quality. Different problem, covered elsewhere.
- Latency, except where a probe times out, which is a transient condition and produces no verdict.
- Whether the source system's ACLs are themselves *correct*. The tool verifies that the index agrees
  with the source system. Whether the source system reflects the organisation's intent is a
  different audit and `tearline` takes no position on it.
