# 2026-09-03 — tearline runs, and what a first run does not always find

Implemented propagation, drift, and differential retrieval. Eight scenarios, sixteen variants, all
passing; ruff, strict mypy, 28 tests green.

## Sixteen variants passed on the first run, and that is not the compliment it looks like

`whence`'s first run found four problems within a minute. This one found none, and the reason is
instructive rather than flattering: `scripts/validate_fixtures.py` had been checking these
expectations against **its own implementation of the same entitlement rule** since the first
scenario was authored. The design had already met code — just not the code that would ship.

So the lesson from `whence` holds with a correction. It is not that implementing finds design
errors; it is that *executing* does. A checker written while authoring is execution, and it had
already flushed out the arithmetic mistakes that would otherwise have surfaced today.

The cost was a duplicate predicate. Two implementations of the same rule drift, and the drift shows
up as confident disagreement between the fixture checker and the tool — which is exactly the class
of failure this project exists to report about *other* systems. `validate_fixtures.py` now imports
from `tearline.rules`, and keeps a narrower job: checking that hand-authored expectations are
arithmetically consistent while a scenario is being written, before there is any question of what
the tool does with them.

## The test that failed was mine

`test_a_clean_variant_never_produces_a_finding` failed on `boundary-crossing-chunk/clean`, and it
was right to. That variant *correctly* reports `c-0051` as `unverifiable`: a chunk whose entitlement
cannot be verified is reported with its reason rather than silently counted as fine.

I had conflated **finding** with **fault**. "Clean" forbids a `contradicted` verdict and any
retrieval delta. It does not forbid a finding, and a tool that emitted nothing for a clean variant
would be hiding the very abstention DEC-015 was written to make visible.

Renamed the test and wrote the distinction into it, because it is the kind of thing that gets
re-broken by someone tidying up later.

## What the evaluator refuses to claim

Thirty-seven entries across the negative sets are prose — `must_not_conclude: "retrieval is working
correctly because nothing leaked"`, `"the tenant boundary is broken"`, and so on. They forbid
*claims*, and this tool emits no narrative, so they are vacuously satisfied.

The evaluator counts them and prints that they were not machine-checked, rather than folding them
into the pass. A negative set that silently scores as passed is the same overclaiming the project
exists to prevent, appearing in the instrument.

That number is also a useful signal about the corpus: over a third of the authored negative material
guards against conclusions rather than outputs, which is a fair reflection of where the damage
actually happens — a finding phrased one level too broad costs an audit of the wrong system.

## Scope, stated plainly

Verification runs against fixtures. Backend adapters do not exist, so nothing has touched a real
index or source system. The two backends are decided (DEC-017, DEC-018) and chosen for contrast —
engine-enforced and application-enforced — and until one is built, every result here is a statement
about the model, not a measurement of a deployment.

## Open next

- A backend adapter. Postgres with `pgvector` and RLS is the harder and more interesting one,
  because its residual risk is completeness rather than confidentiality, and `post-filter-truncation`
  exists to catch exactly that.
- Whether `Verdict` should be imported from `attestrun` rather than declared here. Raised and not
  yet decided; coupling four repos so they can share three words may cost more in standalone
  legibility than it saves.
