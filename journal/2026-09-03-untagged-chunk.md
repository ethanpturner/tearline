# 2026-09-03 — untagged-chunk, and a fault the fixture format could not express

Second fixture. It needed a capability the format did not have, which is becoming the reliable
pattern: authoring finds what specifying does not.

## The fault is in two places, and only one was expressible

`wrong-tenant-tag` puts its fault in the data — a chunk carries the wrong tenant — so "what the
system returns" and "the stated rule applied to the index" are the same computation. The whole
fixture format quietly assumed that.

`untagged-chunk` breaks the assumption. A chunk arrives with no entitlement metadata, and what
happens next depends entirely on the enforcement layer:

- Under the stated rule, `unknown` grants nothing, so the chunk is withheld from **everyone** —
  including the finance analyst genuinely entitled to it. Nothing leaks.
- Under a filter that reads absence as no-restriction, nothing excludes the chunk, so it reaches
  **everyone** — including a principal in a different tenant.

Same index, byte for byte. One line of difference in how it is enforced. So the scenario has three
variants, and `faulted/` and `faulted-naive/` differ only in a declared `filter`.

DEC-013 makes that a closed set implemented in the checker rather than free-form, for the reason
DEC-010 gives backends: a fixture that can describe enforcement in free form can prove anything,
since the author writes both the bug and the expectation. Verified by trying it — declaring
`filter: whatever-i-want` is rejected rather than silently accepted.

## The latent case is the one worth having

I expected the naive-filter variant to be the interesting one. It is the more alarming, but the
`faulted/` variant is the more useful.

Under correct enforcement the fault produces no leak at all. Its only symptom is under-retrieval —
and the symptom **points away from the problem**. It reads as a retrieval gap. An operator who
follows it concludes the analyst lacks permissions, widens a grant that was already correct, and
the untagged chunk stays untagged until it meets a filter that admits it.

So `faulted/expected-clean.yaml` forbids the conclusion *"retrieval is working correctly because
nothing leaked"*, and forbids *"p-acme-fin has insufficient permissions"*. Both are what a competent
person would conclude from the evidence in front of them, and both are wrong.

That is the second time under-retrieval has carried a finding invisible to a leak-hunting tool.
DEC-008 argued it as a completeness problem; here it is an early warning about a leak that has not
happened yet.

## Two things I had to think carefully about

**Why `contradicted` and not `unverifiable`,** given the chunk's state is literally `unknown`. The
claim under test is *this chunk carries the entitlement its source states*. The source states one,
the chunk carries none, the claim is false. Nothing about the instrument was limited. What is
unknown is what the index *intended*, and the tool does not ask that. Reaching for `unverifiable`
because a field is named `unknown` would confuse a property of the data with a limit of the
measurement — the same confusion DEC-001 guards, running the other way.

**What still works in the naive variant.** `c-0041`, the correctly tagged sibling from the same
document, is properly excluded from the globex principal by tenant and from the acme engineer by
role, in the same run. The tenant boundary is not broken. It is never consulted for a chunk that
declines to mention one. So the expectations forbid *"the tenant boundary is broken"* — a claim
that sends someone to audit a working mechanism, when the true statement is narrower and fixable.

Getting that right mattered more than it first appeared. A verifier's findings are read by people
under time pressure, and a finding phrased one level too broad costs an audit of the wrong system.

## The checker got stronger

It now computes truth from the source documents, visible from the index under the declared
enforcement, and both deltas — then checks all three against the authored file. Re-running it
against `wrong-tenant-tag` under the stronger check still passed, which is some evidence the earlier
expectations were right for the right reasons rather than by luck.

Tested the negative paths again before trusting it: suppressing a real leak in the answer key is
caught, and so is an undeclared enforcement model.

## Open next

- `boundary-crossing-chunk`. Still the one that decides whether this is a real tool, and now the
  only sketched scenario whose expected output is `unverifiable` rather than a finding. Worth doing
  while the concern about it being a disposal route is fresh.
- Backends by decision (DEC-010).
