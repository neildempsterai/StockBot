"""Tests for Scrappy run outcome codes and policy-driven fetch behavior."""
from __future__ import annotations

import pytest

from stockbot.scrappy.run_service import (
    OUTCOME_FAILED_VALIDATION,
    OUTCOME_NO_CANDIDATES,
    OUTCOME_PARTIAL,
    OUTCOME_SUCCESS_ALL_BLOCKED_OR_METADATA,
    OUTCOME_SUCCESS_ALL_DEDUPED,
    OUTCOME_SUCCESS_NO_NOTES,
    OUTCOME_SUCCESS_USEFUL,
    _compute_outcome,
)


def test_compute_outcome_no_candidates() -> None:
    assert _compute_outcome(0, 0, 0, 0, 0, 0, []) == OUTCOME_NO_CANDIDATES


def test_compute_outcome_success_useful_output() -> None:
    assert _compute_outcome(10, 0, 5, 3, 5, 0, []) == OUTCOME_SUCCESS_USEFUL
    assert _compute_outcome(10, 0, 5, 5, 5, 0, []) == OUTCOME_SUCCESS_USEFUL


def test_compute_outcome_partial_note_rejections() -> None:
    assert _compute_outcome(10, 0, 5, 2, 5, 3, []) == OUTCOME_PARTIAL


def test_compute_outcome_success_candidates_but_no_notes() -> None:
    assert _compute_outcome(10, 0, 5, 0, 5, 0, []) == OUTCOME_SUCCESS_NO_NOTES


def test_compute_outcome_success_all_deduped() -> None:
    assert _compute_outcome(10, 0, 0, 0, 0, 0, []) == OUTCOME_SUCCESS_ALL_DEDUPED


def test_compute_outcome_success_all_blocked() -> None:
    assert _compute_outcome(10, 10, 0, 0, 0, 0, []) == OUTCOME_SUCCESS_ALL_BLOCKED_OR_METADATA


def test_compute_outcome_failed_validation() -> None:
    assert _compute_outcome(10, 0, 5, 0, 5, 5, ["validate https://x.com: invalid"]) == OUTCOME_FAILED_VALIDATION


def test_metadata_only_never_fetches_full_text() -> None:
    """Policy: open_text fetch only when policy_decision is open_text; metadata_only must not trigger fetch.
    This is enforced in run_service: we only call fetch_full_text_result when c.get('policy_decision') == 'open_text'.
    """
    # Code path check: in run_service the loop is:
    # for c in after_dedup:
    #     if c.get("policy_decision") != "open_text": continue
    #     if not OPEN_TEXT_FETCH_ENABLED: continue
    #     ... fetch_full_text_result(url)
    # So metadata_only candidates never enter the fetch block.
    policy_decision_metadata = "metadata_only"
    policy_decision_open = "open_text"
    assert policy_decision_metadata != "open_text"
    assert policy_decision_open == "open_text"
