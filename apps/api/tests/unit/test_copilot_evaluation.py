import json
from pathlib import Path

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
    predictions = [
        {
            "stage": "presale",
            "intent": "recommendation",
            "risk_level": "high",
            "handoff_required": True,
            "citation_ids": ["sku-1"],
            "recommended_sku_code": "APPLE-001",
        },
        {
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
    assert metrics.factual_error_rate == 0.5


def test_evaluation_zero_denominators_return_zero() -> None:
    metrics = evaluate_predictions([], [])

    assert metrics.stage_accuracy == 0.0
    assert metrics.intent_accuracy == 0.0
    assert metrics.high_risk_recall == 0.0
    assert metrics.citation_validity == 0.0
    assert metrics.factual_error_rate == 0.0


def test_jsonl_loader_rejects_malformed_input(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text(json.dumps({"message": "missing fields"}) + "\nnot-json\n", encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="line 1"):
        load_jsonl(path, kind="expected")
