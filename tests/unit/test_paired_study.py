"""The paired-study truth set and its observed columns hold the shape the page relies on."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "docs" / "eval" / "paired-study"

EXPECTED_CAUGHT_BY = {"reviewer", "tearline", "both", "neither"}
TEARLINE_CAUGHT = {"yes", "no", "refused"}
SEMGREP_CAUGHT = {"yes", "no", "partial"}
AXES = {"propagation", "drift", "differential"}
# A key named for content would be the DEC-002 breach; the files hold identifiers and locators.
CONTENT_KEYS = {"text", "content", "excerpt", "chunk_text", "body", "snippet"}


def _load(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((STUDY / name).read_text())
    return loaded


def _walk_keys(node: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            keys.add(str(k))
            keys |= _walk_keys(v)
    elif isinstance(node, list):
        for item in node:
            keys |= _walk_keys(item)
    return keys


def test_every_matrix_row_is_observed_and_nothing_else() -> None:
    matrix = {r["id"] for r in _load("matrix.yaml")["rows"]}
    observed = {r["id"] for r in _load("observed.yaml")["rows"]}
    assert matrix == observed


def test_matrix_rows_carry_the_closed_vocabulary() -> None:
    for row in _load("matrix.yaml")["rows"]:
        assert row["expected_caught_by"] in EXPECTED_CAUGHT_BY, row["id"]
        for field in ("target", "branch_or_commit", "fault", "tearline_scenario", "reasoning"):
            assert row[field], f"{row['id']} lacks {field}"


def test_observed_rows_carry_the_closed_vocabulary() -> None:
    for row in _load("observed.yaml")["rows"]:
        assert row["tearline"]["caught"] in TEARLINE_CAUGHT, row["id"]
        assert set(row["tearline"].get("axes", [])) <= AXES, row["id"]
        assert row["semgrep"]["caught"] in SEMGREP_CAUGHT, row["id"]
        if row["semgrep"]["caught"] == "no":
            assert row["semgrep"]["rule"] is None, row["id"]
        else:
            assert row["semgrep"]["rule"], row["id"]
        for column in ("mantis", "codex_security"):
            assert row[column] == {"status": "not-run"}, row["id"]


def test_no_file_in_the_study_carries_a_content_field() -> None:
    for name in ("matrix.yaml", "observed.yaml"):
        assert not (_walk_keys(_load(name)) & CONTENT_KEYS), name


def test_the_rules_file_parses_and_every_rule_states_its_floor() -> None:
    rules = _load("semgrep-rules.yaml")["rules"]
    assert len(rules) == 8
    for rule in rules:
        assert rule["metadata"]["floor"] in {
            "generic",
            "semi-generic",
            "fault-shaped",
            "app-shaped",
        }


def test_the_page_quotes_the_counts_the_files_hold() -> None:
    matrix = _load("matrix.yaml")["rows"]
    observed = {r["id"]: r for r in _load("observed.yaml")["rows"]}
    ragref = [r for r in matrix if r["target"] == "ragref"]
    assert len(ragref) == 8
    tearline_expected = {r["id"] for r in ragref if r["expected_caught_by"] in {"tearline", "both"}}
    tearline_caught = {r["id"] for r in ragref if observed[r["id"]]["tearline"]["caught"] == "yes"}
    assert tearline_expected == tearline_caught
    assert len(tearline_caught) == 6
    semgrep_caught = [r["id"] for r in ragref if observed[r["id"]]["semgrep"]["caught"] != "no"]
    assert len(semgrep_caught) == 3
    page = (ROOT / "docs" / "eval" / "paired-study.md").read_text()
    for phrase in ("6 of 8", "3 of 8", "8 of 8"):
        assert phrase in page
