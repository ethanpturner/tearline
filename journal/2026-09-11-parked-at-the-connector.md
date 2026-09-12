# Parked at the connector

The tool stops here, and the reason is worth writing down carefully, because "we stopped" and "it
did not work" read the same in a repository six months later and they are not the same thing.

Everything measured this week says the gap is real. Glean documents its own permission syncs taking
up to 28 days. Microsoft documents Restricted Content Discovery taking over a week and calls it a
temporary governance control. Both vendors publish the staleness of the thing this tool measures,
and neither measures it. The enforcement engines — Cerbos, OpenFGA, SpiceDB — generate the filter
and never ask whether the tag it filters on is true. Knostic probes at the answer layer, closed,
without reading the index or counting what was withheld. Nothing is a test framework for
entitlements, and `docs/eval/real-targets.md` is, as far as anyone has published, the first
measurement of a real one.

Then the delivery question, which the evidence answers differently. Entitlement does not live on a
POSIX filesystem. It lives in SharePoint, Drive, Confluence and Snowflake, and reaching any of them
is an OAuth application, a permissions model, a tenant-admin consent flow, and an obligation to
keep all of that working as four vendors change four APIs on their own schedules. One connector is
a quarter of work and a tax that never ends. Four is the shape that ends single-maintainer
projects, and it ends them quietly: the tool keeps building, the integrations rot one at a time,
and the measurements nobody can reproduce any more get cited as though they were current.

So the choice was to commit to one system deeply or to stop at the boundary already demonstrated.
Stopping is recorded as DEC-025, and the Microsoft Graph adapter — the one that would have come
next, and the one whose absence is most conspicuous — is written up as an issue with what it would
actually take. An issue is a better record than an empty directory. It says the thing was
considered, costed, and declined, which is a different claim from not having thought of it.

What the park protects is the part that needs no vendor's cooperation. The offline corpus replays
with no service at all: sixteen variants, zero false positives over 74 derived negative-set
subjects. The live figures are captured and dated rather than continuously re-run, and they say
what they say — 8 of 8 probes over-retrieving before a real fix and 1 of 8 under-retrieving after
it, on a real application, which is the completeness regression a leak-only verifier scores as
perfect. That finding does not expire because a connector was not written.

The cost is real and belongs in the record: the entitlement gap stays open, and nothing here closes
it. It is not this project's to close alone.
