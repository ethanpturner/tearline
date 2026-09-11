# 2026-09-10 — Who catches what, written down before the reviewers run

The two real applications and the reference app now sit in one place: `docs/eval/paired-study/`.
The truth set says, per fault, which of a code reviewer and this tool is expected to catch it; the
observed file records what each column actually saw. Two columns are filled, `tearline` and a
Semgrep floor. Two are `not-run`, the model reviewers, and the shape of the file does not change
when they land.

## Moving the truth

ragref carried its own `truth/matrix.yaml`, written before any tool ran against the branches. That
was the right order and the wrong place: a truth set belongs beside the scenarios it references
and the tool it scores, not in the target's repository where a reviewer pointed at the code would
read the answer key. It moved here verbatim, and ragref now holds a pointer.

The rag_api rows are not in that order, and the matrix header says so. They were written from pull
request #319's own description of what it closed, after this tool had already run against the
pre-fix and post-fix commits and before any model reviewer had. Stating the order is cheaper than
pretending it was the other one, and the expectations for those rows are the pull request's, not a
reading of the results: `both` where a route lists or queries a shared store with no scope,
`reviewer` where the hole is a write or a route the probe recipe never called.

## The floor

Semgrep with rules written knowing the faults catches 3 of 8 and produces one false positive on
every branch, including `main`. The false positive is the interesting one. A nearest-neighbour
`ORDER BY ... LIMIT` with no tenant predicate in the same statement is a fault on Qdrant and a
non-event on pgvector with row-level security, and a pattern cannot tell which store it is looking
at because the policy is not in the file. That is DEC-017's contrast, seen from the rule's side.

The five misses are structural. Drift has no code. An untagged chunk is a missing tag in an
index. A merged chunk names no tenant. A directory standing in for a group is a string standing in
for a string. A README sentence is not code. Whatever the model reviewers do with those rows, the
floor establishes that they are not pattern-shaped, so a catch there is reading, not matching.

## What the counts say about the tool

6 of 8, and both misses are expected: `f-superuser` is a refusal, `f-policy-intent` is agreement
between source and index that evaluation plan section 7 says is not a finding. The number to hold
onto is not the six; it is that the two non-catches are the two rows where a catch would have been
wrong.

## Open

The Mantis and Codex Security columns, once the per-run cost is known. The Qdrant rows still say
what the 2026-09-10 exit-status journal said: the differential axis there runs the verifier's own
filter, so application-side faults reach it only as stored data. Issue #5 carries that.
