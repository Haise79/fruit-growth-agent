from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class EvaluationInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    stage_accuracy: float
    intent_accuracy: float
    high_risk_recall: float
    citation_validity: float
    factual_error_rate: float


_EXPECTED_REQUIRED = {
    "message", "stage", "intent", "risk_level", "handoff_required", "allowed_citation_ids"
}


def load_jsonl(path: Path, *, kind: str) -> list[dict[str, Any]]:
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
        if kind == "expected":
            missing = sorted(_EXPECTED_REQUIRED - value.keys())
            if missing:
                raise EvaluationInputError(
                    f"expected line {number} is missing required fields: {', '.join(missing)}"
                )
            if not isinstance(value["message"], str) or not value["message"].strip():
                raise EvaluationInputError(f"expected line {number} has an invalid message")
            if not isinstance(value["allowed_citation_ids"], list):
                raise EvaluationInputError(
                    f"expected line {number} allowed_citation_ids must be a list"
                )
        rows.append(value)
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
    for row, prediction in _pairs(expected, predictions):
        citations = prediction.get("citation_ids", [])
        if isinstance(citations, list) and all(citation in set(row["allowed_citation_ids"]) for citation in citations):
            valid += 1
    return _ratio(valid, len(expected))


def factual_error_rate(expected: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> float:
    return _ratio(sum(prediction.get("recommended_sku_code") != row.get("expected_sku_code") for row, prediction in _pairs(expected, predictions)), len(expected))


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
