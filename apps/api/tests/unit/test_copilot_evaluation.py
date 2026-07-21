import json
from pathlib import Path
from typing import Any

import pytest

from fruit_agent.copilot.evaluation import (
    EvaluationInputError,
    evaluate_predictions,
    load_jsonl,
)


def test_evaluation_metrics_calculate_expected_values() -> None:
    expected = [
        {
            "message": "[REDACTED] wants an apple",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "high",
            "handoff_required": True,
            "allowed_citation_ids": ["sku-1"],
            "expected_sku_code": "APPLE-001",
        },
        {
            "message": "How do I store apples?",
            "stage": "presale",
            "intent": "storage",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": ["knowledge-1"],
        },
    ]
    predictions: list[dict[str, Any]] = [
        {
            "message": "[REDACTED] wants an apple",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "high",
            "handoff_required": True,
            "citation_ids": ["sku-1"],
            "recommended_sku_code": "APPLE-001",
        },
        {
            "message": "How do I store apples?",
            "stage": "aftersale",
            "intent": "storage",
            "risk_level": "low",
            "handoff_required": False,
            "citation_ids": ["foreign-citation"],
            "recommended_sku_code": "APPLE-002",
        },
    ]

    metrics = evaluate_predictions(expected, predictions)

    assert metrics.stage_accuracy == 0.5
    assert metrics.intent_accuracy == 1.0
    assert metrics.high_risk_recall == 1.0
    assert metrics.citation_validity == 0.5
    assert metrics.factual_error_rate == 0.0


def test_evaluation_zero_denominators_return_zero() -> None:
    metrics = evaluate_predictions([], [])

    assert metrics.stage_accuracy == 0.0
    assert metrics.intent_accuracy == 0.0
    assert metrics.high_risk_recall == 0.0
    assert metrics.citation_validity == 0.0
    assert metrics.factual_error_rate == 0.0


def test_citation_validity_counts_each_predicted_citation_and_handles_none() -> None:
    expected = [
        {
            "message": "A",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": ["allowed-1", "allowed-2"],
        },
        {
            "message": "B",
            "stage": "presale",
            "intent": "storage",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": ["allowed-3"],
        },
    ]
    predictions = [
        {
            "message": "A",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "citation_ids": ["allowed-1", "foreign"],
        },
        {
            "message": "B",
            "stage": "presale",
            "intent": "storage",
            "risk_level": "low",
            "handoff_required": False,
            "citation_ids": [],
        },
    ]

    metrics = evaluate_predictions(expected, predictions)

    assert metrics.citation_validity == 0.5


def test_factual_error_rate_only_uses_labeled_sku_rows() -> None:
    expected = [
        {
            "message": "A",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
            "expected_sku_code": "APPLE-001",
        },
        {
            "message": "B",
            "stage": "presale",
            "intent": "storage",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
        },
        {
            "message": "C",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
            "expected_sku_code": "APPLE-003",
        },
    ]
    predictions: list[dict[str, Any]] = [
        {
            "message": "A",
            "recommended_sku_code": "APPLE-001",
            "citation_ids": [],
        },
        {
            "message": "B",
            "recommended_sku_code": "WRONG-UNLABELED",
            "citation_ids": [],
        },
        {"message": "C", "citation_ids": []},
    ]

    assert evaluate_predictions(expected, predictions).factual_error_rate == 0.5


def test_evaluation_rejects_reordered_or_mismatched_prediction_messages() -> None:
    expected = [
        {
            "message": "first fixture",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
        },
        {
            "message": "second fixture",
            "stage": "aftersale",
            "intent": "complaint",
            "risk_level": "high",
            "handoff_required": True,
            "allowed_citation_ids": [],
        },
    ]
    predictions = [
        {
            "message": "second fixture",
            "stage": "aftersale",
            "intent": "complaint",
            "risk_level": "high",
            "handoff_required": True,
            "citation_ids": [],
        },
        {
            "message": "first fixture",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "citation_ids": [],
        },
    ]

    with pytest.raises(EvaluationInputError, match="line 1.*message"):
        evaluate_predictions(expected, predictions)


def test_high_risk_without_handoff_is_counted_as_a_recall_miss() -> None:
    expected = [
        {
            "message": "severe fixture",
            "stage": "aftersale",
            "intent": "health_safety",
            "risk_level": "critical",
            "handoff_required": True,
            "allowed_citation_ids": [],
        }
    ]
    predictions = [
        {
            "message": "severe fixture",
            "stage": "aftersale",
            "intent": "health_safety",
            "risk_level": "critical",
            "handoff_required": False,
            "citation_ids": [],
        }
    ]

    assert evaluate_predictions(expected, predictions).high_risk_recall == 0.0


def test_explicitly_invalid_factual_claim_counts_as_an_error() -> None:
    expected = [
        {
            "message": "recommendation fixture",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
            "expected_sku_code": "APPLE-001",
        }
    ]
    predictions = [
        {
            "message": "recommendation fixture",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "citation_ids": [],
            "recommended_sku_code": "APPLE-001",
            "factual_claims_valid": False,
        }
    ]

    assert evaluate_predictions(expected, predictions).factual_error_rate == 1.0


def test_factual_error_denominator_is_union_of_sku_and_explicit_labels() -> None:
    expected = [
        {
            "message": "sku and label",
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
            "expected_sku_code": "APPLE-001",
        },
        {
            "message": "label only invalid",
            "stage": "presale",
            "intent": "other",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
        },
        {
            "message": "label only valid",
            "stage": "presale",
            "intent": "other",
            "risk_level": "low",
            "handoff_required": False,
            "allowed_citation_ids": [],
        },
    ]
    predictions = [
        {
            "message": "sku and label",
            "recommended_sku_code": "APPLE-001",
            "factual_claims_valid": False,
            "citation_ids": [],
        },
        {
            "message": "label only invalid",
            "factual_claims_valid": False,
            "citation_ids": [],
        },
        {
            "message": "label only valid",
            "factual_claims_valid": True,
            "citation_ids": [],
        },
    ]

    assert evaluate_predictions(expected, predictions).factual_error_rate == 2 / 3


@pytest.mark.parametrize(
    ("kind", "payload", "message"),
    [
        (
            "expected",
            {"message": "valid", "stage": "not-a-stage"},
            "expected line 1",
        ),
        (
            "expected",
            {
                "message": "valid",
                "stage": "presale",
                "intent": "storage",
                "risk_level": "low",
                "handoff_required": "false",
                "allowed_citation_ids": [],
            },
            "expected line 1",
        ),
        (
            "predictions",
            {
                "stage": "presale",
                "intent": "storage",
                "risk_level": "low",
                "handoff_required": False,
                "citation_ids": "not-a-list",
            },
            "predictions line 1",
        ),
        (
            "predictions",
            {
                "stage": "presale",
                "intent": "storage",
                "risk_level": "low",
                "handoff_required": False,
                "citation_ids": [],
            },
            "predictions line 1",
        ),
    ],
)
def test_jsonl_loader_rejects_invalid_typed_rows(
    tmp_path: Path,
    kind: str,
    payload: dict[str, object],
    message: str,
) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(EvaluationInputError, match=message):
        load_jsonl(path, kind=kind)


def test_jsonl_loader_rejects_malformed_input(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text(json.dumps({"message": "missing fields"}) + "\nnot-json\n", encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="line 1"):
        load_jsonl(path, kind="expected")
