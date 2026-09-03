# untagged-chunk

**What this measures.** DEC-003 — that an absent entitlement is `unknown` and never permissive —
and that the same ingestion fault is latent or catastrophic depending on enforcement.

**The fault.** Chunk `c-0042` reaches the index with no entitlement metadata. Its source document,
`doc-004`, is restricted to tenant `acme` and role `finance`.

## Three variants, because the data fault is not the whole story

| Variant | Index | Enforcement | Outcome |
|---|---|---|---|
| `clean/` | tagged | stated rule | nothing |
| `faulted/` | `c-0042` untagged | stated rule | propagation finding; **under-retrieval**, no leak |
| `faulted-naive/` | `c-0042` untagged | absence read as no-restriction | propagation finding; **cross-tenant leak** |

`faulted/` and `faulted-naive/` have byte-identical chunk data. They differ in one line: the
declared `filter`. That is the scenario's argument — the same index is safe or compromised depending
on a property of the enforcement layer that no amount of inspecting the data will reveal.

## The latent case is the interesting one

Under correct enforcement, the untagged chunk is withheld from *everyone*, including the finance
analyst who is genuinely entitled to it. Nothing leaks. The only symptom is under-retrieval — and it
**points away from the real problem**. It looks like a retrieval gap. An operator following the
symptom concludes the analyst lacks permissions, widens a grant that was already correct, and the
untagged chunk stays untagged until it meets a filter that admits it.

That is why `faulted/expected-clean.yaml` forbids the conclusion *"retrieval is working correctly
because nothing leaked."* A tool that reports only realised disclosures passes this index, and then
the same data gets served by a system one line different.

It is also the second scenario in which under-retrieval carries a finding a leak-hunting tool cannot
see. That was DEC-008's argument; this is the case where it protects against a *future* leak rather
than a present withholding.

## The enforcement bug, precisely

The naive filter is not a strawman. It is what "filter by tenant" looks like when written directly:
exclude a chunk when its stated restriction excludes the principal, and otherwise admit. A chunk
with no tenant and no role has no stated restriction, so nothing excludes it, so everyone gets it.

Note what still works in that variant. `c-0041` — the correctly tagged sibling from the same
document — is properly excluded from the globex principal by tenant and from the acme engineer by
role, in the same run. **The tenant boundary is not broken.** It is simply never consulted for a
chunk that declines to mention one. `faulted-naive/expected-clean.yaml` forbids the broader claim,
because "the tenant boundary is broken" sends someone to audit a mechanism that is working.

## Why `contradicted` and not `unverifiable`

Worth stating, since the chunk's state is literally `unknown`. The claim under test is *this chunk
carries the entitlement its source document states*. The source states one; the chunk carries none;
the claim is false. Nothing about the instrument was limited, so the verdict is `contradicted`.

What is unknown is what the index *intended*, and that is not a question the tool asks. Reaching for
`unverifiable` because the field is named `unknown` would confuse a property of the data with a
limit of the measurement — which is the distinction DEC-001 exists to keep sharp in the other
direction.

## What authoring this changed

The fixture format had no way to express an enforcement fault. `wrong-tenant-tag` puts its fault in
the data, so "what the system returns" and "the rule applied to the index" are the same thing. Here
they are not, and they must not be conflated.

Variants now declare a `filter`, drawn from a closed set implemented in the checker and grown by
decision — the same treatment DEC-010 gives backends, and for the same reason: a filter model that
could be written freely in a fixture would let a scenario prove whatever it liked. Recorded as
DEC-013.

## Pass condition

**All variants:** propagation findings exactly as authored; nothing from `expected-clean.yaml`; no
`unverifiable` anywhere.

**`faulted/`:** under-retrieval of `c-0042` for `p-acme-fin`, no over-retrieval for anyone.

**`faulted-naive/`:** over-retrieval of `c-0042` for both `p-acme-eng` and `p-globex-eng`, and
`c-0041` correctly excluded from both.
