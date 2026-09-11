# Real targets: two RAG applications at pre-fix and post-fix versions

*Provenance: live, captured 2026-09-10 against local installs; not replayable in CI. The result
files under `results/` are the tool's own JSON reports, identifiers only. Everything that wrote to
a store lived outside this repository; `tearline` was imported read-only at `f443540`.*

Two open-source retrieval applications were stood up at the commit before and after a real
authorization fix, and `tearline`'s three axes were run against their indexes. The question was
not whether the fixes work — the projects' own tests say so — but what a verifier that reads the
deployed index sees at each version, and whether it sees anything the fix's authors did not.

No embedding model was involved. A local HTTP shim answered the applications' embedding calls with
a deterministic 16-dimensional vector derived from the sha256 of the input, the same construction
`backends/base.py::deterministic_vector` uses for probes, so relevance was out of the loop
(DEC-011) and no provider key existed anywhere in the environment.

## LibreChat `rag_api` (pgvector), pull request #319

Pre-fix commit `4985b37`, the parent of #319. Post-fix commit `f426560`, "scope every document read
and delete by owner", merged 2026-08-15. The pull request closed six holes; the two that reach the
index are that `GET /ids` listed every file to any authenticated caller and `POST /query_multiple`
performed no authorization, and that a chunk with no recorded `user_id` read as belonging to
everyone.

Corpus: four single-chunk files, two uploaded as `alice`, two as `bob`. The historical fault was
planted directly: after ingest, the second of alice's chunks had its `user_id` removed from the
chunk metadata. Entitlement rule, in the closed vocabulary (DEC-021): tenant ignored, role
ignored, direct `principal-listed`, combined `tenant AND role AND direct`, which reduces to owner
only. Source of truth for ownership: the uploader ledger, supplied in-harness because no shipped
source adapter reads an application table (see gaps below). The differential axis called the
application as a client, `GET /ids` then `POST /query_multiple` over every id, once as each of the
two principals, four probes each.

| | pre-fix `4985b37` | post-fix `f426560` |
|---|---|---|
| chunks examined | 4 | 4 |
| chunks untraceable | 0 | 0 |
| propagation: planted null-owner chunk | `contradicted`, cause `undetermined` | `contradicted`, cause `undetermined` |
| probes run | 8 | 8 |
| probes over-retrieving | 8 of 8 | 0 of 8 |
| chunks over-retrieved, summed over probes | 16 | 0 |
| probes under-retrieving | 0 of 8 | 1 of 8 |
| probes clean | 0 of 8 | 7 of 8 |

Pre-fix, every probe over-retrieves: each principal receives every other principal's chunks, which
is the disclosure #319 closed.

Post-fix, the leak is gone. Every cross-owner probe returns nothing, and alice's probe for her first
file returns exactly that file.

The one under-retrieval is the fix's own breaking change, and only the completeness axis reports
it. Post-fix, a chunk with no `user_id` is owned by nobody and is no longer readable. The planted
chunk belongs to alice in the source ledger, so alice can no longer retrieve her own document. A
verifier that measures leaks scores the post-fix index as perfectly secure. `tearline` reports
`under-retrieval` on that probe, which is the DEC-008 failure: confidentiality holds, completeness
fails silently, and a generation step handed no context answers anyway. The propagation axis flags
the same chunk independently, because its stored entitlement is `unknown` (DEC-003) while the
source says it has an owner. The cause is `undetermined` because no timestamp separates a
propagation fault from a later change (DEC-006), and that is the honest label for a chunk whose
metadata was removed after ingest.

## Open WebUI (Qdrant multitenancy), CVE-2026-44560

Versions 0.8.12, the last affected, and 0.9.0, the fix. Two files were ingested through Open
WebUI's own vector-store client into the multitenancy layout, owned by two users. The physical
collection `open-webui_files` carries `tenant_id` equal to the logical collection name
(`file-<id>`) and the owner in `metadata.user_id`, at both versions.

Store-layer search returns a hit with no access check at both versions. The boundary is the
application: 0.9.0 gates every `file-*` collection behind `has_access_to_file` inside
`get_sources_from_items`, and 0.8.12 appends the collection name and queries with no check. The
fix for the CVE lives in the application, not the store, which is DEC-018's description of Qdrant
("isolation is application-supplied") observed on a real advisory rather than on a fixture.

The differential axis did not run end to end here. The shipped Qdrant adapter reads `tearline`'s
own payload schema and raises `KeyError: 'chunk_id'` against this collection, and a faithful probe
would have to issue the application's own authorized query rather than the store's, which needs
the application's user and file tables populated through its model layer. Both are adapter gaps,
recorded below, not findings about Open WebUI.

**Correction to the plan this work came from.** The plan assumed an environment flag,
`BYPASS_RETRIEVAL_ACCESS_CONTROL`, that could switch access control off in a fixed version.
No such flag exists in 0.8.12 or 0.9.0. The only toggle between leaking and not is the version.

## What the two targets say together

- A real fix introduced a real completeness failure, and the leak-only reading of the index misses
  it. That is the case DEC-008 was written for, now shown on a merged pull request rather than a
  fixture.
- A real CVE fix landed in the application layer above a store that enforces nothing, exactly as
  DEC-018 says Qdrant deployments must. A verifier that reads only the store cannot see the fix,
  and a verifier that reads only the application cannot see what the store would hand to anyone
  who bypasses it.
- The `unknown` entitlement path (DEC-003) behaved correctly against a real store: a chunk with no
  owner became `contradicted`, never a pass.

## Adapter gaps this exposed

Each is filed as an issue phrased as the decision it needs: #2, #3, #4, and #5.

1. **No ownership-ledger source.** `FilesystemSource` is the only source (DEC-020). Both
   applications state ownership in a table, not on a file. Touches DEC-005 (what is ground truth)
   and DEC-010's rule that an adapter is added by decision.
2. **No application-level retrieve adapter.** Both applications enforce at their retrieval
   endpoint. Probing the store directly measures a boundary the application never exposes.
   Touches DEC-018.
3. **The Qdrant adapter assumes `tearline`'s payload schema.** A real multitenancy collection
   uses its own field names. A payload map declared by the target would keep DEC-012's rule that
   the target states the rule, extended to the shape of its own index.
4. **The live paths pass only the tenant to the store**, while truth is computed from the full
   rule. Recorded in the 2026-09-10 journal; needs its own decision.

## Files

- `ragapi/target.yaml`, `ragapi/shared/*.yaml`: the target description a future adapter would
  consume; not loadable by `tearline scan` today, for the reasons above.
- `openwebui/target.yaml`, `openwebui/shared/*.yaml`: the same for Open WebUI.
- `results/ragapi-pre.json`, `results/ragapi-post.json`: the verification reports, identifiers
  only.
