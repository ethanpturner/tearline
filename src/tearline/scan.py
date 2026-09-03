"""Running against a real system rather than a fixture.

A fixture scenario supplies documents, chunks and retrieval results, all authored. That is what
makes the evaluation honest -- truth is known -- and it is also its limit: nothing authored can
demonstrate that the tool reads a real ACL or observes a real store's answer.

A scan replaces three of those four with live reads. The **source system** supplies documents, the
**backend** supplies the index inventory and answers the probes, and only the probes themselves
remain authored, because relevance is not under test (DEC-011) and choosing which chunks *should*
come back is a statement about the corpus that no store can make on the tool's behalf.

The entitlement rule is read from the target directory, not guessed (DEC-012), and the tool writes
nothing to either system (DEC-004).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tearline.backends.base import Backend, RetrievalRequest, deterministic_vector
from tearline.domain import Principal, Probe, VerificationReport
from tearline.entitlement_rule import load_rule
from tearline.fixtures import Scenario, Variant, load_principals, load_probes
from tearline.sources import FilesystemSource
from tearline.verify import verify

#: Dimensionality of the pseudo-embedding. Fixed rather than configurable: the vector carries no
#: semantics (DEC-011), so its width is a property of the store's schema and not a tuning knob.
DIMENSIONS = 16


class ScanError(ValueError):
    """The target description is missing something the scan cannot proceed without."""


@dataclass(frozen=True)
class Target:
    """What a scan points at. Read from `target.yaml` beside a `shared/` directory."""

    source: FilesystemSource
    backend: Backend
    enforcement: str
    ann_limit: int | None


def _source(raw: dict[str, Any], base: Path) -> FilesystemSource:
    kind = raw.get("kind")
    if kind != "filesystem":
        raise ScanError(f"unknown source kind {kind!r}; `filesystem` is the only adapter (DEC-020)")
    mapping = raw.get("group_to_tenant")
    if not isinstance(mapping, dict) or not mapping:
        raise ScanError(
            "the source states no `group_to_tenant` mapping. DEC-020 requires it to be supplied "
            "for the reason DEC-012 gives about entitlement rules: a mapping guessed from group "
            "names is quietly wrong for every organisation that names groups differently, and its "
            "wrongness surfaces as confident findings about the index."
        )
    root = (base / str(raw.get("root", "."))).resolve()
    if not root.is_dir():
        raise ScanError(f"source root {root} is not a directory")
    return FilesystemSource(root=root, group_to_tenant={str(k): str(v) for k, v in mapping.items()})


def _backend(raw: dict[str, Any]) -> Backend:
    kind = raw.get("kind")
    if kind == "qdrant":
        from tearline.backends.qdrant import COLLECTION, QdrantBackend

        return QdrantBackend(
            str(raw["base_url"]), collection=str(raw.get("collection", COLLECTION))
        )
    if kind == "pgvector":
        import psycopg

        from tearline.backends.pgvector import PgVectorBackend

        admin = raw.get("admin_dsn")
        return PgVectorBackend(
            psycopg.connect(str(raw["dsn"])),
            # The propagation axis needs to see rows no principal can see -- exactly the population
            # where a mislabelling hides -- so it reads through a connection that may bypass the
            # policy. Without one the scan still runs the differential axis and says so.
            admin_connection=psycopg.connect(str(admin)) if admin else None,
        )
    raise ScanError(f"unknown backend kind {kind!r}; `qdrant` and `pgvector` are supported")


def load_target(path: Path) -> Target:
    raw = yaml.safe_load((path / "target.yaml").read_text()) or {}
    for key in ("source", "backend"):
        if not isinstance(raw.get(key), dict):
            raise ScanError(f"target.yaml has no `{key}:` mapping")
    return Target(
        source=_source(raw["source"], path),
        backend=_backend(raw["backend"]),
        enforcement=str(raw.get("enforcement", "rule")),
        ann_limit=raw.get("ann_limit"),
    )


def scan(path: Path, target: Target) -> VerificationReport:
    """Read both systems and verify the index against the source.

    Every chunk in the index is examined, including ones no probe mentions: the propagation axis is
    an inventory comparison and a mislabelled chunk nobody happens to query is still mislabelled.
    """
    scenario = Scenario(
        slug=path.name,
        documents=target.source.documents(),
        principals=load_principals(path / "shared" / "principals.yaml"),
        probes=load_probes(path / "shared" / "probes.yaml"),
        rule=load_rule(path / "shared" / "entitlement-rule.yaml"),
    )
    variant = Variant(
        name="live",
        chunks={chunk.id: chunk for chunk in target.backend.chunks()},
        enforcement=target.enforcement,
        ann_limit=target.ann_limit,
    )

    def retrieve(probe: Probe, principal: Principal, limit: int | None) -> list[str]:
        return target.backend.retrieve(
            RetrievalRequest(
                vector=deterministic_vector(probe.query, DIMENSIONS),
                principal=principal,
                # No declared limit means ask for the whole index. Asking for fewer would let the
                # tool's own truncation register as the store's under-retrieval (DEC-019).
                limit=limit or max(len(variant.chunks), 1),
            )
        )

    return verify(
        scenario, variant, retrieve=retrieve, enforcement_site=target.backend.enforcement_site
    )
