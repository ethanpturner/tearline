"""Backend adapters.

A backend is the seam between `tearline`'s verification logic and a real index. Each one is added
by its own decision-log entry recording **where isolation is enforced** -- in the engine, or in
application code -- because the two have very different failure modes, and an abstraction hiding
the difference would encourage the assumption that the engine is on the operator's side (DEC-010).

Relevance is not what this tool tests (DEC-011). An adapter is asked for the chunks a query returns
*for a principal*; whether those were the most relevant ones is somebody else's question, and the
query vector is supplied rather than computed so no embedding model is needed to check a boundary.
"""

from __future__ import annotations

from tearline.backends.base import Backend, RetrievalRequest, deterministic_vector

__all__ = ["Backend", "RetrievalRequest", "deterministic_vector"]
