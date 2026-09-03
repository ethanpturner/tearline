# 2026-09-03 — Wiring the tool to real systems, and what that exposed

An audit read every decision against the code. The headline finding was blunt: **nothing connected
the CLI to a backend.** `Backend.retrieve()` had no caller anywhere in `src/`, the Protocol was
never checked against either adapter, and `run_probes` computed its results entirely from the
fixture's authored `matches` — so the verification core could not have accepted a live store even if
one had been passed to it.

Meanwhile `README.md` said "verified against a real index" and `CLAUDE.md` said "Backend adapters
are not built, so nothing has yet run against a real index." Both were in the repository at HEAD.
That is worse than either statement alone: a reader who checks one document and stops has no way to
know which one they got.

## What got built

`tearline scan` runs the three axes against a real system. `verify` takes a retrieval callable, so
the differential axis observes what a store actually returned rather than what a fixture asserts,
and every report carries `enforcement_site` — because a clean result means one thing when the
database held the boundary and a different thing when the retrieval code did.

## DEC-012 was written down and not enforced

It forbids a default entitlement predicate, on the grounds that systems combine tenant, roles and
direct grants differently and a hardcoded one reports its own wrong assumption as findings about the
index. `shared/entitlement-rule.yaml` existed in all eight scenarios, was cited in three docstrings,
and was read by nothing. The predicate was in `rules.py`.

The rule now loads from the fixture and a missing one is an error. The vocabulary it composes from
is closed (DEC-021), for DEC-013's reason: a rule expressive enough to say anything lets its author
write both the bug and the expectation, and a passing scenario then shows only that two authored
artifacts agree. It is also, less abstractly, an execution surface in a tool whose subject is what a
system should let a caller reach.

## DEC-004 was a promise about call sites

"The tool is read-only against every system it touches," and both adapters carried `TRUNCATE chunks`
and `DELETE /collections/...`. Those moved to `tests/live/harness.py`. Read-only enforced by where
the code lives survives a caller's mistake; read-only enforced by convention survives until someone
calls the method.

## The finding that came out of testing the new path

The first end-to-end test of a live scan crashed — a probe naming a chunk the index does not hold,
which cannot happen in a fixture and is how an ingestion gap arrives in reality. Fixing that
surfaced the more interesting one underneath.

A chunk with no source document, returned to a principal, was going into `over_retrieved`. That
field carries `verdict: contradicted`, which asserts the principal was not entitled to what they
received. **Nothing establishes that.** The propagation axis already calls such a chunk
`unverifiable`; the probe axis was calling the same chunk a leak.

`orphaned-chunk` had noticed. Its truth set labelled the row `over-retrieval` and attached a note
reading "Not a claim that a disclosure occurred." DEC-016 had already settled which of those a
reader acts on — findings are read quickly and under pressure, and a disclaimer in a `why:` field
does not survive being pasted into a ticket. A tool whose output needs a footnote to stop meaning
the wrong thing has chosen the wrong output. DEC-022 records the reversal.

## The scorer, again

Six authored keys read as nothing: `inherits:` was ignored in four files, `must_not_flag` was
counted as unscorable prose, and an unrecognised `expected_unverifiable` subject was silently
skipped. All are checked now, and an unrecognised subject fails rather than passes.

Making `must_not_flag` machine-checked gave the false-positive count a denominator, which is why
`evaluate` now prints "0 of 3" rather than a rate. 0 of 3 and 0 of 3000 are the same figure and not
the same evidence, and the first is what this corpus supports.

## And a small one worth keeping

Splitting the write path out meant tests that build an index take the privileged connection as a
fixture. One did not declare it, so the name bound the fixture *function* rather than its value:
no import error, nothing from ruff or mypy, and an `AttributeError` minutes later once the service
container was up. The offline suite could not see it, because the live tests are the only place
either adapter runs. A test now parses `tests/live/` for the pattern — the class of bug is cheap to
catch and expensive to wait for.

## What is open

A scan has not been pointed at a production-scale corpus, or at any store but the two. The
`enforcement_site` distinction is reported but its consequences are argued rather than measured:
DEC-017 predicts under-retrieval on the engine-enforced backend and DEC-018 over-retrieval on the
application-enforced one, and nothing here has yet observed either at scale.
