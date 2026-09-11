# 2026-09-10 — Two real fixes, read from the index

The corpus so far was fixtures and two CI containers holding a few dozen points. Today the tool
was pointed at two applications other people wrote, each at the commit before and after a fix
they shipped: LibreChat's `rag_api` around pull request #319, and Open WebUI around
CVE-2026-44560. The stores ran locally without Docker, on Homebrew Postgres with pgvector and a
Qdrant release binary, and a sha256 shim answered every embedding call so no model was involved.
The page is `docs/eval/real-targets.md`; the numbers there are the tool's own reports.

## The fix that broke something

Before #319, `rag_api` listed every file to any caller and queried without authorization. The
tool sees that as it should: 8 of 8 probes over-retrieve. After #319, none do. That much the
project's own tests already knew.

What they did not record is that the fix changed the meaning of a chunk with no owner. Before, it
belonged to everyone; after, to nobody. The planted null-owner chunk in the corpus belonged to
alice in the source ledger, and post-fix alice cannot retrieve her own document. The report shows
one `under-retrieval`, and nothing else in the run distinguishes the post-fix index from a perfect
one. DEC-008 said a system that returns nothing is not a secure system. This is the first time the
tool has shown that on a change somebody merged rather than on a variant somebody authored, and it
is the sentence the README now leads with in the measurement paragraph.

The propagation axis flagged the same chunk from the other side, `unknown` against a stated owner,
cause `undetermined`. Nothing had to be tuned for a real store; DEC-003's refusal to read absence
as a grant did the work.

## The fix that lives in the wrong layer to see from the store

Open WebUI's store returns a hit with no access check at 0.8.12 and at 0.9.0. The fix is one
function call in the application. DEC-018 predicted this shape for Qdrant deployments in the
abstract; a CVE made it concrete. It also stopped the differential axis: the shipped adapter reads
this project's own payload schema and raised `KeyError` on the first point it saw, and a faithful
probe would have to go through the application's endpoint, which the tool has no adapter for.

## What the plan got wrong

The plan this came from assumed an environment flag that would turn access control off in a fixed
Open WebUI version. It does not exist in either version examined. The correction is written into
the results page rather than quietly dropped, because a plan that names a control that is not
there is the kind of claim this project exists to catch.

## Open

Four adapter gaps are filed as issues, each phrased as the decision it needs: an ownership-ledger
source, an application-level retrieve adapter, a payload map for foreign Qdrant collections, and
the tenant-only live path from the previous entry. None is a one-line fix, and none should land
without a decision-log entry, because each changes what the tool claims to have checked.
