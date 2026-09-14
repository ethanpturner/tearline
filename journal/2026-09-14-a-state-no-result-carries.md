# 2026-09-14 — A state no result carries

A sweep across the sibling repositories for checks that cannot come out false reached this one
today. The class is a check whose failing branch is unreachable: it runs, it passes, and it
establishes nothing. Six had turned up elsewhere in two days, which is a rate rather than luck,
so all five trees were audited rather than another feature written.

This repository is parked (DEC-025), so the audit records and does not change. The page is
`docs/architecture/unfailable-checks.md`.

## What it found

One thing, and it does not touch a measurement. `ProbeOutcome.NOT_RUN` is declared and nothing
assigns it. A probe that cannot run — fewer than two identities, DEC-007 — never becomes a
`ProbeResult` at all; it goes into a separate `skipped` list and surfaces as `probes_skipped`. The
mechanism works. The enum member that looks like it is the mechanism is vestigial, and the
`not-run` line a reader sees in the output is printed from the other field.

What that costs is a schema promise: `outcome` is serialised, so a consumer generating a type from
the emitted document gets a state that never arrives, and does not learn that skipped probes live
somewhere else. The fix is one line. Parked means not taking it, because a parked project making
small schema changes is not parked, and nothing reads the schema today.

## What it cleared, and why that mattered more

Two load-bearing claims came through this cleanly, and both did so because somebody had already
done the work the audit was looking for.

"The adapters contain no write path" has a test that walks the AST and was mutation-proved against
three planted shapes on 2026-09-10 — including an f-string write head that the earlier version of
the same test had passed. That is the difference between an invariant and a sentence about one.

"0 false positives over 74 negative-set subjects" carries its own falsifiability proof in DEC-023:
a planted error fires 31 of the 74. A zero that a mutation can move is a measurement; a zero that
nothing can move is a description of the harness.

The audit's standing question is the second one generalised. For every published number: what
input would change it. Both figures here answer it in writing, next to the figure.
