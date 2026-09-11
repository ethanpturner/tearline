# 2026-09-10 — The exit status was lying

An external reading of the repository, done to decide whether `tearline scan` could serve as a
reproduction oracle for a code-review harness, found four things in an afternoon that five sessions
of building had not. Three were defects; one was a framing.

## The exit status

`_cmd_scan` returned `1 if (report.propagation or report.partial) else 0`. Every probe result was
printed and none of them was consulted. So `post-filter-truncation/truncating` — the scenario
written to make DEC-008's point, where every tag is correct and one tenant receives nothing —
exited 0. So did an over-retrieval on a clean inventory, which is DEC-018's failure exactly.

The text report was right in both cases. The exit status is what a pipeline reads. A tool whose
whole argument is that a confidentiality result must not be read as a completeness result had an
exit code that collapsed the two. DEC-024 states the rule; `exit_status` is its one implementation.

## The inventory cap

`QdrantBackend.chunks()` issued one scroll with `limit: 1000`. A collection of 1,001 points reported
`chunks_examined: 1000`. The 1,001st was never compared against its source, and nothing said so.
`chunks_examined` is a claim the report makes about its own coverage; a page size made it false
silently. It pages now, and a fake store with 2,001 points checks that it does.

Neither CI container has ever held more than a few dozen points, which is why nobody saw it. The
live harness needs a run at a few thousand before anyone quotes a coverage number from a real scan.

## The guard that read only literals

`test_a_shipped_adapter_contains_no_write` checked the head of every string constant and the verb
of every `_request` call. An f-string is not a constant in the AST; `cursor.execute(stmt)` with
`stmt` built elsewhere has no readable head; a `_request` whose path is a variable cannot be
classified as a read endpoint. All three passed the guard. Each was added to the adapters in turn
and the strengthened test fails on each; then they were removed. DEC-004 says read-only is
structural. It was structural against the shapes someone had thought of.

## `--json`

There was no machine-readable output. There is now, and it is `VerificationReport.model_dump_json()`
and nothing else — no field is added on the way out, so DEC-002 holds for it by construction rather
than by a second review. The test checks the keys are the model's declared fields and that no
document label from the fixture reaches the output.

## The framing

The survey that prompted this found nothing that reconciles a deployed index against its source or
measures under-retrieval on one. It also found the three kinds of tool that sit beside this one:
authorization engines that generate the filter, sync ledgers that record a sync ran, and one closed
product that tests oversharing across user profiles at the answer layer. And it found ARBITER, the
only prior work that counts over-restriction as an error. The README now names them. "Nothing like
this exists" was true and unhelpful; "these exist and here is the line between them and this" is
what a reader can check.

## Open

The live paths communicate only the tenant to the store — `set_config(PRINCIPAL_SETTING, tenant)`
on Postgres, a `tenants` match on Qdrant — while truth is computed from the full rule of tenant and
role or direct grant. Roles and direct grants are never enforced live, and nothing in `target.yaml`
lets an operator name the policy's expected setting or payload key. That is a design gap, not a
one-line fix, and it needs its own decision.
