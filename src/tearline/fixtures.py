"""Loading a scenario. Nothing under a variant's `expected-*` files is read here (DEC-009)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tearline.domain import Chunk, Entitlement, EntitlementState, Principal, Probe, SourceDocument


def _entitlement(raw: dict[str, Any] | None) -> Entitlement:
    raw = raw or {}
    return Entitlement(
        state=EntitlementState(raw.get("state", "unknown")),
        tenants=frozenset(raw.get("tenants") or []),
        roles=frozenset(raw.get("roles") or []),
        principals=frozenset(raw.get("principals") or []),
        classification=raw.get("classification"),
    )


@dataclass(frozen=True)
class Scenario:
    slug: str
    documents: dict[str, SourceDocument]
    principals: dict[str, Principal]
    probes: tuple[Probe, ...]


@dataclass(frozen=True)
class Variant:
    name: str
    chunks: dict[str, Chunk]
    enforcement: str
    ann_limit: int | None


def load_scenario(path: Path, slug: str) -> Scenario:
    shared = path / "shared"
    docs = yaml.safe_load((shared / "documents.yaml").read_text())
    system = str(docs.get("system", "unknown"))
    documents = {
        str(d["id"]): SourceDocument(
            id=str(d["id"]),
            system=system,
            label=d.get("label"),
            acl_modified_at=d.get("acl_modified_at"),
            entitlement=_entitlement(d.get("entitlement")),
        )
        for d in docs["documents"]
    }
    principals = {
        str(p["id"]): Principal(
            id=str(p["id"]),
            label=str(p.get("label", p["id"])),
            tenant=p.get("tenant"),
            roles=frozenset(p.get("roles") or []),
        )
        for p in yaml.safe_load((shared / "principals.yaml").read_text())["principals"]
    }
    probes = tuple(
        Probe(
            id=str(p["id"]),
            query=str(p["query"]),
            principals=tuple(p["principals"]),
            matches=tuple(p["matches"]),
        )
        for p in yaml.safe_load((shared / "probes.yaml").read_text())["probes"]
    )
    return Scenario(slug=slug, documents=documents, principals=principals, probes=probes)


def load_variant(path: Path, name: str) -> Variant:
    raw = yaml.safe_load((path / name / "index.yaml").read_text())
    chunks = {
        str(c["id"]): Chunk(
            id=str(c["id"]),
            source_document_ids=tuple(c.get("source_document_ids") or []),
            ingested_at=c.get("ingested_at"),
            entitlement=_entitlement(c.get("entitlement")),
        )
        for c in raw["chunks"]
    }
    return Variant(
        name=name,
        chunks=chunks,
        enforcement=str(raw.get("filter", "rule")),
        ann_limit=raw.get("ann_limit"),
    )


def variants_of(path: Path) -> list[str]:
    return sorted(d.name for d in path.iterdir() if d.is_dir() and (d / "index.yaml").exists())
