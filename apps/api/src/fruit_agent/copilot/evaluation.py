from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictStr,
    ValidationError,
    field_validator,
)


class EvaluationInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    stage_accuracy: float
    intent_accuracy: float
    high_risk_recall: float
    citation_validity: float
    factual_error_rate: float


EvaluationStage = Literal["presale", "aftersale", "unknown"]
EvaluationIntent = Literal[
    "product_info",
    "recommendation",
    "gift",
    "delivery",
    "storage",
    "damage",
    "refund",
    "complaint",
    "health_safety",
    "other",
]
EvaluationRisk = Literal["low", "medium", "high", "critical"]


class _ExpectedEvaluationRow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: StrictStr
    stage: EvaluationStage
    intent: EvaluationIntent
    risk_level: EvaluationRisk
    handoff_required: StrictBool
    allowed_citation_ids: list[StrictStr]
    expected_sku_code: StrictStr | None = None

    @field_validator("message", "expected_sku_code")
    @classmethod
    def nonblank_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value


class _PredictionEvaluationRow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: StrictStr
    stage: EvaluationStage
    intent: EvaluationIntent
    risk_level: EvaluationRisk
    handoff_required: StrictBool
    citation_ids: list[StrictStr]
    recommended_sku_code: StrictStr | None = None

    @field_validator("message", "recommended_sku_code")
    @classmethod
    def nonblank_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value


def load_jsonl(path: Path, *, kind: str) -> list[dict[str, Any]]:
    if kind not in {"expected", "predictions"}:
        raise EvaluationInputError("kind must be 'expected' or 'predictions'")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise EvaluationInputError(f"{kind} input must be UTF-8") from exc
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationInputError(f"{kind} line {number} is not valid JSON") from exc
        if not isinstance(value, dict):
            raise EvaluationInputError(f"{kind} line {number} must be a JSON object")
        row_model = _ExpectedEvaluationRow if kind == "expected" else _PredictionEvaluationRow
        try:
            rows.append(row_model.model_validate(value).model_dump())
        except ValidationError as exc:
            raise EvaluationInputError(f"{kind} line {number} is invalid: {exc}") from exc
    return rows


def _ratio(matches: int, total: int) -> float:
    return matches / total if total else 0.0


def _pairs(
    expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]
) -> Iterator[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    if len(expected) != len(predictions):
        raise EvaluationInputError("expected and prediction JSONL files must contain the same number of rows")
    return zip(expected, predictions, strict=True)


def stage_accuracy(expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> float:
    return _ratio(sum(row["stage"] == prediction.get("stage") for row, prediction in _pairs(expected, predictions)), len(expected))


def intent_accuracy(expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> float:
    return _ratio(sum(row["intent"] == prediction.get("intent") for row, prediction in _pairs(expected, predictions)), len(expected))


def high_risk_recall(expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> float:
    high_risk = [(row, prediction) for row, prediction in _pairs(expected, predictions) if row["risk_level"] in {"high", "critical"}]
    return _ratio(sum(prediction.get("risk_level") in {"high", "critical"} for _, prediction in high_risk), len(high_risk))


def citation_validity(expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> float:
    valid = 0
    total = 0
    for row, prediction in _pairs(expected, predictions):
        citations = prediction.get("citation_ids", [])
        if not isinstance(citations, list):
            continue
        allowed = set(row["allowed_citation_ids"])
        valid += sum(citation in allowed for citation in citations)
        total += len(citations)
    return _ratio(valid, total)


def factual_error_rate(expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> float:
    labeled_pairs = [
        (row, prediction)
        for row, prediction in _pairs(expected, predictions)
        if row.get("expected_sku_code") is not None
    ]
    return _ratio(
        sum(
            prediction.get("recommended_sku_code") != row["expected_sku_code"]
            for row, prediction in labeled_pairs
        ),
        len(labeled_pairs),
    )


def evaluate_predictions(expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> EvaluationMetrics:
    return EvaluationMetrics(
        stage_accuracy=stage_accuracy(expected, predictions),
        intent_accuracy=intent_accuracy(expected, predictions),
        high_risk_recall=high_risk_recall(expected, predictions),
        citation_validity=citation_validity(expected, predictions),
        factual_error_rate=factual_error_rate(expected, predictions),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate offline copilot predictions against JSONL fixtures.")
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    args = parser.parse_args()
    metrics = evaluate_predictions(
        load_jsonl(args.expected, kind="expected"), load_jsonl(args.predictions, kind="predictions")
    )
    print(json.dumps(asdict(metrics), sort_keys=True))


if __name__ == "__main__":
    main()
