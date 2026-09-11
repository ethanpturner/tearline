"""The Qdrant inventory read pages until the store says there is no more.

Until 2026-09-10 `chunks()` issued one scroll with `limit: 1000` and stopped. A collection of 1,001
points reported `chunks_examined: 1000`, and the 1,001st -- wherever the store chose to put it in
scroll order -- was never compared against its source document. The number of chunks examined is a
claim the report makes about its own coverage, and a fixed page size made it wrong silently.
"""

from __future__ import annotations

from typing import Any

from tearline.backends.qdrant import SCROLL_PAGE, QdrantBackend


class PagingStore(QdrantBackend):
    """Answers scroll requests from an in-memory list, honouring `limit` and `offset` the way the
    real endpoint does: `next_page_offset` is the id of the first point not returned, or absent."""

    def __init__(self, count: int) -> None:
        super().__init__("http://unused:6333")
        self._points = [
            {"id": i, "payload": {"chunk_id": f"c-{i:05d}", "entitlement_state": "unknown"}}
            for i in range(count)
        ]
        self.calls: list[dict[str, Any]] = []

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        assert method == "POST" and path.endswith("/points/scroll") and body is not None
        self.calls.append(body)
        start = int(body.get("offset", 0))
        page = self._points[start : start + int(body["limit"])]
        result: dict[str, Any] = {"points": page}
        if start + len(page) < len(self._points):
            result["next_page_offset"] = start + len(page)
        return {"result": result}


def test_the_inventory_read_follows_the_offset_past_one_page() -> None:
    store = PagingStore(SCROLL_PAGE * 2 + 1)
    chunks = store.chunks()
    assert len(chunks) == SCROLL_PAGE * 2 + 1
    assert len(store.calls) == 3
    assert "offset" not in store.calls[0] and store.calls[1]["offset"] == SCROLL_PAGE
    assert chunks[-1].id == f"c-{SCROLL_PAGE * 2:05d}"


def test_a_single_page_is_read_in_one_call() -> None:
    store = PagingStore(3)
    assert len(store.chunks()) == 3
    assert len(store.calls) == 1
