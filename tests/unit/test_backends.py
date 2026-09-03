"""The backend seam: that it is one, and that nothing behind it writes.

Neither adapter can be exercised without a live store, so these tests do what can be checked without
one -- that both satisfy the `Backend` protocol, that the two enforcement sites are distinct, and
that DEC-004's read-only guarantee is structural rather than a promise about how the code is called.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from tearline.backends.base import Backend, deterministic_vector
from tearline.backends.pgvector import PgVectorBackend
from tearline.backends.qdrant import QdrantBackend

ADAPTERS = (PgVectorBackend, QdrantBackend)
#: SQL that changes a store. Matched against the *start* of a string literal rather than anywhere
#: inside one: this module's own prose contains most of these words while explaining their absence,
#: and a substring match would make the test unable to describe what it checks.
SQL_WRITES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "CREATE", "ALTER", "GRANT", "COPY")
#: HTTP methods that change a store, as passed to an adapter's `_request`.
HTTP_WRITES = ("PUT", "POST", "PATCH", "DELETE")


@pytest.mark.parametrize("adapter", ADAPTERS, ids=lambda a: a.__name__)
def test_the_adapter_satisfies_the_backend_protocol(adapter: type[Backend]) -> None:
    """`Backend` is a Protocol, so nothing checks this at runtime unless something asks.

    Before this test the protocol was decorative: both adapters happened to match it and neither was
    ever checked against it, so a renamed method would have been caught by whichever call site
    noticed first, or by nobody. Members are checked by name and arity rather than with
    `issubclass`, which refuses a protocol carrying a data member -- and `enforcement_site` is one.
    """
    for name in ("chunks", "retrieve"):
        expected = inspect.signature(getattr(Backend, name))
        actual = inspect.signature(getattr(adapter, name))
        assert list(actual.parameters) == list(expected.parameters), f"{adapter.__name__}.{name}"
    assert isinstance(adapter.enforcement_site, str)


def test_the_two_backends_enforce_in_different_places() -> None:
    """The reason there are two (DEC-018). A pair that both trusted the engine would let the tool
    assume the store is on the operator's side, which is exactly what Qdrant does not do."""
    assert {a.enforcement_site for a in ADAPTERS} == {"engine", "application"}


def test_a_shipped_adapter_contains_no_write() -> None:
    """DEC-004: the tool is read-only against every system it touches.

    A verifier that writes is a verifier that can cause the incident it is looking for. The schema
    and the fixture load live in `tests/live/harness.py`, out of the shipped package -- because
    read-only enforced by where the code lives survives a caller's mistake, and read-only enforced
    by convention does not.
    """
    for path in sorted(Path("src/tearline").rglob("*.py")):
        tree = ast.parse(path.read_text())
        # Docstrings are excluded by identity, not by pattern: this module's prose names every one
        # of these statements while explaining why none of them is here, and a substring match on
        # comments would make the test unable to describe itself.
        docstrings = {
            id(n.body[0].value)
            for n in ast.walk(tree)
            if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef)
            and n.body
            and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstrings:
                    continue
                head = node.value.strip().upper()
                for statement in SQL_WRITES:
                    assert not head.startswith(statement), f"{path}: {statement} reached src/"
            # An HTTP adapter writes by method, not by SQL. The method is the first argument.
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr != "_request" or not node.args:
                    continue
                verb = node.args[0]
                assert isinstance(verb, ast.Constant), f"{path}: computed HTTP method"
                assert verb.value not in HTTP_WRITES or _is_read_endpoint(node), (
                    f"{path}: a {verb.value} reached src/"
                )

    for adapter in ADAPTERS:
        source = inspect.getsource(adapter)
        for method in ("apply_schema", "load"):
            assert f"def {method}(" not in source, f"{adapter.__name__}.{method} is a write path"


def _is_read_endpoint(call: ast.Call) -> bool:
    """A POST that reads. Qdrant's search and scroll endpoints are POSTs carrying a query body,
    which is a read however the verb reads -- the write test would otherwise be unable to
    distinguish a search from a load, and would have to be switched off for this adapter."""
    if len(call.args) < 2:
        return False
    path = call.args[1]
    if isinstance(path, ast.JoinedStr):
        parts = [
            v.value for v in path.values if isinstance(v, ast.Constant) and isinstance(v.value, str)
        ]
        return any(p.endswith(("/points/search", "/points/scroll")) for p in parts)
    return False


def test_the_query_vector_carries_no_semantics_and_is_stable() -> None:
    """Relevance is not under test (DEC-011). The vector must be the same across a fixture run and
    a live one, or the two are not comparable; it must not encode meaning, or the tool would be
    judging retrieval quality while claiming to judge entitlement."""
    assert deterministic_vector("a probe", 16) == deterministic_vector("a probe", 16)
    assert deterministic_vector("a probe", 16) != deterministic_vector("a probe.", 16)
    assert len(deterministic_vector("a probe", 32)) == 32
    assert all(-1.0 <= v <= 1.0 for v in deterministic_vector("a probe", 16))
