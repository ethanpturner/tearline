# Benchmarks

Layout and rules are specified in `docs/architecture/evaluation-plan.md`. Three things matter most
and are repeated here because they are the easiest to get wrong.

**Nothing under a scenario's `expected/` is supplied to the tool during a run.**

**Every scenario runs twice** — against the version carrying its planted fault, and against the
clean version where the tool must find nothing. A scenario without its clean twin measures recall
and says nothing about false positives.

**The four expected files are not interchangeable.** `expected-propagation.yaml` and
`expected-visibility.yaml` score detection. `expected-clean.yaml` scores false positives.
`expected-unverifiable.yaml` scores honesty: cases where a confident verdict is wrong even though
nothing is broken.

`scenarios.yaml` is the authoritative list. A directory not registered there is not part of the set.
