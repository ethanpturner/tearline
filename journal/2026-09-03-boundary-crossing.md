# 2026-09-03 — boundary-crossing-chunk: keeping abstention narrow

The scenario I flagged three sessions ago as the one that decides whether this is a real tool. It
was, and for a reason I had not anticipated.

## The trap, from both directions

`doc-005` is shared with acme and globex; `doc-006` is acme only; chunk `c-0051` is drawn from both.
The source system assigns ACLs to documents and has never had an opinion about an object made from
several of them. Chunking manufactured a question nobody answered.

Every other scenario compares a tag against a stated ACL. Here there is none, and the temptation
runs both ways.

Assert an answer and the tool invents policy. The intersection is the safe reading, and it is still
a *choice* — an organisation might reasonably decide a merged chunk inherits the more permissive
parent, or that merging across differing ACLs should be refused at ingestion. DEC-012 already
rejects hardcoding a permission semantic and reporting the mismatch as findings; this would be the
same error in a new place.

Abstain freely and `unverifiable` becomes a shrug. This is the concern I had written down in the
evaluation plan — that "genuine ambiguity" is the obvious disposal route for inconvenient failures —
and this scenario is where it would first be exercised.

## The resolution

**Indeterminacy about the right answer is not indeterminacy about every wrong one.**

A chunk contains material from all of its sources, so a principal may see it only if entitled by all
of them. That intersection is a floor no correct entitlement can go below — the safe bound. It is
not necessarily the right tag, and it is a bound the right tag must respect whatever the policy
turns out to be.

So the tool abstains on exactly one question, *is this tag correct*, and answers the operationally
important one, *does it disclose anything no source permits*. A tag equal to the intersection is
`unverifiable`. A tag exceeding it is `contradicted`.

What makes this enforceable rather than aspirational is the last clause of DEC-015: `unverifiable`
is **unavailable** when the tag exceeds the safe bound. The sources diverge identically in both
variants, so a tool keying abstention on divergence alone abstains in both — including on a tag
granting globex access to material no source grants it. And that abstention would look principled.
`faulted/expected-propagation.yaml` carries a `forbidden_verdicts` block for exactly this.

## Abstention that still reports

`clean/expected-unverifiable.yaml` is the first non-empty file of its kind here, and `c-0051`
appears among the propagation findings even though nothing is wrong with it. A chunk whose
entitlement cannot be verified is not silently counted as fine: the report names the sources, their
divergence, the bound, and that the tag satisfies it.

The finding also carries `what_is_not_being_claimed`. Writing down what an abstention does not cover
is what stops a reader from over-reading it, and it is much cheaper now than as an explanation
later.

## The negative set caught the subtle failure

`clean/expected-clean.yaml` forbids reporting `c-0051` as *under-retrieved* for the globex
principal. I nearly wrote that expectation the other way. Reporting it would require the tool to
assert globex should see the chunk — the precise policy call it had just declined to make.

Abstaining on a question and then implying an answer through a neighbouring finding is the subtlest
way to lose the discipline, and it would have been invisible in the propagation output. Worth
remembering that the negative sets are where that class of error surfaces.

## What authoring changed

`source_document_id` was singular, so a chunk with two sources could not be represented at all —
and multi-source chunks are ordinary output for pipelines that merge, deduplicate, or window across
boundaries. A singular field also forces a lossy choice at ingestion, discarding exactly the
information needed to compute what a merged chunk may disclose. Now plural (DEC-014), with the three
existing scenarios migrated and re-verified under the change.

## Open next

- `narrowed-after-ingest` and `narrowed-without-timestamps`, the drift pair. The second is where
  cause must resolve `unverifiable` rather than be guessed, so it is the next test of the same
  discipline this scenario just established.
- Backends by decision (DEC-010). Four scenarios in, the fixture format has stopped changing every
  session, which is roughly the signal that it is ready to meet a real store.
