# 2026-09-03 — The drift pair, and a word doing two jobs

`narrowed-after-ingest` and `narrowed-without-timestamps`. Same divergence, one difference: whether
the source system tells you when its ACLs last changed.

## Both directions in one run

Both documents changed on 2026-03-01; the index was built on 2026-02-01 and never rebuilt. One
source narrowed and one broadened, so `p-globex-eng` is simultaneously over-served and under-served
by the same stale index, in the same probe.

That is not a contrived pairing. It is what a re-indexing lapse looks like once any ACL churn has
happened in both directions, which is the normal state of an organisation. And it defeats two
plausible tool designs at once: one that reports only leaks sees half the run, and one that pools
over- and under-retrieval into a single score reports it as net-zero.

`c-0071` is the enterprise oversharing pattern in miniature, and worth stating precisely because the
framing is so easy to get wrong. Nothing was breached. No credential was stolen. No filter failed. A
permission was tightened and the index did not hear about it, and the retrieval layer then enforced,
faithfully, a grant that no longer existed.

## The word doing two jobs

I wrote the second scenario's finding out — `verdict: contradicted, cause: unverifiable` — and it
read as a self-contradiction.

It was not. Verdict and cause are different axes. *Do the index and the source disagree* is
answerable from two values. *How did they come apart* needs timestamps, and this source system has
none. Both answers were as strong as the evidence supported.

But DEC-006 had named the cause value `unverifiable`, colliding with the `Verdict` value of the same
name, and the collision invites exactly the failure the scenario exists to catch: letting
uncertainty about *why* swallow certainty about *what*. That loss runs in the reassuring direction,
since an `unverifiable` verdict reads as "nothing established here."

Renamed to `undetermined` (DEC-016). Small change, and one that only appeared because I wrote the
finding out and read it back rather than reasoning about the enum in the abstract.

## The failure worth guarding

`drifted/expected-propagation.yaml` forbids three ways out, and the two guesses are more interesting
than the abstention.

Guessing `drift` is plausible — it is the commoner cause — and it sends an operator to re-index. If
the truth is a pipeline bug, the re-index reproduces the same wrong tag and the finding returns,
now with the appearance of having been investigated. Guessing `propagation-fault` costs an audit of
a working pipeline while the index stays stale.

Neither guess is detectably wrong to the person acting on it. That is what makes the abstention
worth enforcing rather than merely preferring: the cost of a confident wrong cause is paid by
someone who has no way to know they were misdirected.

And this is the common case, not a corner. Many source systems expose no ACL modification time, so
`undetermined` will be emitted constantly — which is why the shape has to read as complete rather
than apologetic. The finding is not weaker for being unattributed.

## The negative set again

`drifted/expected-clean.yaml` forbids ranking the `c-0081` finding below the `c-0071` one. They are
one defect with two symptoms, and ranking them invites fixing the leak while leaving the staleness,
which leaves the leak's cause in place.

That is the third scenario running where the sharpest requirement is in the negative set rather than
the positive one. The positive sets say what the tool must find; the negative sets say what it must
not conclude, and the conclusions a competent person would reach from partial evidence are where the
damage is.

## Open next

- Backends by decision (DEC-010). Six scenarios in, and the format changed only for the plural-source
  migration in the last two — it has stopped moving, which was the signal I said to wait for.
- `orphaned-chunk`, `post-filter-truncation`, and `single-principal-probe` remain sketched. The last
  is the smallest and pins DEC-007, where "no leak detected" from a one-identity probe is the
  forbidden output.
