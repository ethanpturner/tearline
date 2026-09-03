# narrowed-without-timestamps

**What this measures.** That an undetermined *cause* does not downgrade a determinable *verdict*.

**The setup.** Identical divergence to `narrowed-after-ingest`, with one thing removed: this source
system exposes no `acl_modified_at`, and the index records no `ingested_at`.

## The two axes

The mismatch is plain — the index says one thing, the source says another, and comparing two values
needs no history. What is unavailable is *why* they came apart. The tag may never have matched (a
pipeline bug) or matched once and gone stale (a cadence problem), and nothing here separates them.

So findings carry `verdict: contradicted` with `cause: undetermined`. Both halves are as strong as
the evidence supports, and neither is weakened to match the other.

`drifted/expected-propagation.yaml` forbids the three ways out:

- **`cause: drift`** — a guess, and the plausible one, since drift is commoner. It sends an operator
  to re-index. If the truth is a pipeline bug, the re-index reproduces the same wrong tag and the
  finding returns, now looking as though it has been investigated.
- **`cause: propagation-fault`** — the opposite guess, with the opposite cost: an audit of a working
  pipeline while the index stays stale.
- **`verdict: unverifiable`** — the failure the scenario exists for. Letting uncertainty about *why*
  swallow certainty about *what* discards a real finding, and discards it in the reassuring
  direction, because an `unverifiable` verdict reads as "nothing established here."

## Why this is the common case, not the corner case

Worth stating plainly: many source systems do not expose when an ACL last changed. A tool that can
only report a cause when timestamps exist will emit `undetermined` constantly, which is exactly why
the shape has to be legible rather than apologetic. The finding is not weaker for being unattributed
— the index is still serving a permission the source does not grant.

The report says so, and `drifted/expected-unverifiable.yaml` records the abstention on the cause
axis alongside what remains established, so a reader cannot mistake a withheld attribution for a
withheld finding.

## What authoring this changed

The mismatch cause for "could not be determined" was named `unverifiable`, colliding with the
`Verdict` value of the same name. `verdict: contradicted, cause: unverifiable` reads as a
self-contradiction and invites precisely the collapse the scenario forbids. Renamed to
`undetermined` (DEC-016).

A small change, and the kind that only appears when you write the finding out and read it back.

## Pass condition

Two findings, both `contradicted` with cause `undetermined`; identical retrieval deltas to
`narrowed-after-ingest`; no `drift` or `propagation-fault` cause anywhere; **no `unverifiable`
verdict anywhere**.
