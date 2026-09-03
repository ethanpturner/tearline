# post-filter-truncation

**What this measures.** DEC-008, in its purest form: a finding with no mistagged chunk anywhere.

**The setup.** Four chunks, all correctly entitled. The probe's relevance order puts three acme
chunks first and the single globex chunk fourth. The two variants differ in one integer —
`ann_limit`, the number of candidates the approximate search returns before filtering.

| Variant | `ann_limit` | globex principal receives |
|---|---:|---|
| `clean/` | 4 | `c-0101` |
| `truncating/` | 3 | **nothing** |

## Why this is the scenario a leak-only tool cannot see

`truncating/expected-propagation.yaml` is empty, and the emptiness is the assertion. Every
entitlement matches its source. No propagation fault, no drift, no mislabelled chunk, no boundary
crossed, nothing disclosed to anyone.

The entire finding is on the retrieval axis. A verifier that inspects the data passes this index
completely. A verifier that reports only over-retrieval passes it too. Both emit a clean report for
a system in which one tenant receives nothing at all.

And the empty result does not error. A generation step handed no context answers anyway, from
parametric memory, with nothing to indicate retrieval returned nothing — so the tenant gets a
confident answer with no retrieved basis, which is worse than an error precisely because it looks
like success at every layer.

## The mechanism, and why it belongs to a backend

Filtering applied after an approximate scan discards candidates the index already found, and the
index is never asked for more. On a store where the engine enforces the policy (DEC-017) this is the
realistic residual risk: confidentiality is held by the database, and completeness is what breaks.
The application-enforced backend (DEC-018) keeps its filter inside the graph traversal and fails in
the opposite direction.

Reporting per backend rather than merged is what keeps that visible.

## What the fixture does not establish

Ordering is authored, like `matches` itself (DEC-011). So this shows the tool detects truncation —
not that a particular backend or embedding produces it at a particular `k`. Establishing the latter
needs a live run, and any claim from these results has to say so (DEC-019).

## Pass condition

`truncating/`: no propagation findings at all; under-retrieval of `c-0101` for `p-globex-eng`; the
acme principal clean; nothing from `expected-clean.yaml`, in particular not *"no findings; the index
is correctly configured"*.
