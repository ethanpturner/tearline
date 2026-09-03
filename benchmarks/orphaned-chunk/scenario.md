# orphaned-chunk

**What this measures.** That a chunk which cannot be traced to a source document is `unverifiable`
and counted — never quietly passed, and never accused.

**The fault.** `c-0092` records no source document. **Its tag is left correct on purpose**: it is
identical to its correctly-traced sibling.

That choice is the scenario. If the orphan were also mistagged, a tool could pass by finding the tag
error while never noticing it had no basis to check it. Leaving the tag right removes the
consolation prize — the only correct output is an admission that this chunk could not be verified.

## Neither a pass nor an accusation

The verdict is `unverifiable`, and both neighbouring answers are wrong. `verified` claims a
comparison that never happened. `contradicted` asserts the tag is wrong when nothing suggests it is,
and it happens to be right.

`chunks_untraceable` is reported alongside the findings for the same reason: a low finding count
cannot be read as good news without also reading how much was checkable. `expected-clean.yaml`
forbids "the index is 50% verified" — two chunks, one checkable, and a pass rate invites reading an
unverifiable chunk as half-good.

## Why the retrieval row reads as over-retrieval

`c-0092` is still served to the acme principal, and the expected visibility records that as
over-retrieval. That is not a claim a disclosure occurred. The chunk contributes to no truth set,
because nothing establishes what it should be, so the retrieval cannot be shown to be *permitted*.
The distinction is in the finding's text, and it matters: an operator reading "over-retrieval" as
"leak" would go looking for a boundary failure that is not there.

## Pass condition

One propagation finding on `c-0092`, verdict `unverifiable`, cause `undetermined`, `expected: null`;
`chunks_untraceable: 1`; nothing from the negative set.
