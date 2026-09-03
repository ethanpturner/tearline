"""Source-system adapters.

The source system is ground truth (DEC-005): where the index disagrees, the index is wrong. Until
now every axis compared against authored documents, so nothing had ever read an ACL from a real
system.

A POSIX filesystem is a real one, and a common one -- a large share of retrieval corpora are built
from files on a share or a mounted volume, where the permission that governs a document is the
permission on its file. It also makes **drift observable with real timestamps**: `chmod` after
ingestion moves `st_ctime`, which is exactly the signal DEC-006 uses to separate a drifted ACL from
a propagation fault.
"""

from __future__ import annotations

import grp
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tearline.domain import Entitlement, EntitlementState, SourceDocument

#: Mode bit that marks a file readable by anyone. Mapped to the `everyone` role rather than to a
#: wildcard tenant, because "world readable" is a stated grant and not an absent restriction
#: (DEC-003) -- the distinction the whole model turns on.
WORLD_READABLE = stat.S_IROTH


@dataclass(frozen=True)
class FilesystemSource:
    """Reads document ACLs from POSIX ownership and mode bits.

    `group_to_tenant` is supplied rather than inferred, for the reason DEC-012 gives about
    entitlement rules: a mapping guessed from group names would be quietly wrong for every
    organisation that names groups differently, and its wrongness would surface as confident
    findings that the index disagrees with the source.
    """

    root: Path
    group_to_tenant: dict[str, str]
    system: str = "posix-filesystem"

    def _tenant_for(self, gid: int) -> str | None:
        try:
            group = grp.getgrgid(gid).gr_name
        except KeyError:
            return None
        return self.group_to_tenant.get(group)

    def documents(self) -> dict[str, SourceDocument]:
        """One document per file, keyed by path relative to the root."""
        found: dict[str, SourceDocument] = {}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            info = path.stat()
            tenant = self._tenant_for(info.st_gid)
            roles = {"everyone"} if info.st_mode & WORLD_READABLE else {"member"}
            found[str(path.relative_to(self.root))] = SourceDocument(
                id=str(path.relative_to(self.root)),
                system=self.system,
                label=path.name,
                # st_ctime is the inode change time, which `chmod` moves and a content edit also
                # moves. It is the closest thing POSIX offers to "when the ACL last changed", and
                # calling it exact would overstate it: a file whose contents changed carries a
                # ctime that says nothing about its permissions. Recorded because DEC-006 prefers
                # an approximate timestamp to none -- with none, every mismatch is `undetermined`.
                acl_modified_at=datetime.fromtimestamp(info.st_ctime, tz=UTC),
                entitlement=Entitlement(
                    state=EntitlementState.STATED if tenant else EntitlementState.UNKNOWN,
                    tenants=frozenset({tenant}) if tenant else frozenset(),
                    roles=frozenset(roles) if tenant else frozenset(),
                ),
            )
        return found


def group_names() -> list[str]:
    """Groups the current process belongs to. For building a mapping in a test or a first run."""
    return sorted({grp.getgrgid(gid).gr_name for gid in os.getgroups()})
