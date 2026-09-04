# 2026-09-03 — A denominator worth quoting

The false-positive figure was "0 of 3". Three was the whole negative set, because the scorer matched
only `must_not_flag` entries phrased as *"X is not flagged"* and only three were written that way.

That is a denominator measuring how much prose somebody had typed. The corpus offers far more than
three chances to invent a finding: a scenario with one planted fault and seven correct chunks offers
seven, and every probe row the truth set marks clean is another.

## Deriving it

The negative set is now every chunk examined that `expected-propagation.yaml` does not list as a
finding, plus every `(probe, principal)` row `expected-visibility.yaml` marks clean. 74 subjects
across sixteen variants, zero false positives.

The property that makes it worth doing this way rather than by writing 74 more YAML entries: it
grows with the corpus instead of with the documentation. A scenario added next month contributes its
silent subjects without anyone remembering to.

## Mutation, because a bigger number proves nothing on its own

Two planted errors, both chosen to be the kind the corpus exists to catch rather than arbitrary
breakage.

Flagging every multi-tenant chunk as exceeding its safe bound is the specific mistake
`wrong-tenant-tag` was built around — a document shared across two tenants is the commonest
legitimate pattern in a shared corpus, and treating tenant-crossing as suspicious flags all of them.
Reported as a false positive on the chunks concerned. A spurious under-retrieval on clean probe rows
fires 31 of the 74.

## Getting it wrong first, which is where the real finding was

My first pass gave every authored `must_not_flag` entry a structured "must produce no finding"
subject. That reported five false positives, and none of them were false positives.

`c-0051` is a multi-source chunk that the tool correctly reports as `unverifiable` — sources diverge,
so the correct tag is a policy question the source system has never answered. The negative-set entry
about it says it is *withheld from p-globex-eng*, which is a statement about visibility and says
nothing about whether the chunk produces a finding. I had conflated two different assertions because
they live under the same key.

Reading the rest, most of them are like that: eleven of fourteen assert a visibility outcome, not the
absence of a finding. `expected-visibility.yaml` checks those exhaustively already, row by row. So
they belong in neither bucket — calling them unchecked prose understates what the corpus verifies,
and calling them precision subjects double-counts rows that are already scored. They carry
`covered_by:` and are reported on their own line.

The general shape, which has now come up in all three repositories: **an assertion is only as good as
the question it is actually answering**, and a key name is not that question. `must_not_flag` sounded
like one thing and held two.

## Open

The derived set inherits any error in the positive truth set. A fault the truth set fails to list
becomes a negative subject, and detecting it would score as a false positive — a real inversion, and
the same risk `expected-propagation.yaml` already carries. Both are authored against the fixture
rather than against the tool's output, which is the only thing standing between the corpus and
grading the tool against itself.
