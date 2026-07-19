import pytest

from fruit_agent.model_gateway.schemas import ModelProfile
from fruit_agent.model_gateway.service import (
    NoQualifiedModelError,
    select_model,
)


def _model(
    name: str,
    *,
    cost: float,
    fact_error_rate: float,
    risk_recall: float,
) -> ModelProfile:
    return ModelProfile(
        name=name,
        estimated_cost_per_1k_tokens=cost,
        fact_error_rate=fact_error_rate,
        high_risk_recall=risk_recall,
    )


def test_selects_lowest_cost_qualified_model() -> None:
    candidates = [
        _model(
            "qwen-fast",
            cost=0.001,
            fact_error_rate=0.018,
            risk_recall=0.96,
        ),
        _model(
            "glm-cheap",
            cost=0.0005,
            fact_error_rate=0.025,
            risk_recall=0.97,
        ),
        _model(
            "qwen-pro",
            cost=0.003,
            fact_error_rate=0.010,
            risk_recall=0.99,
        ),
    ]

    assert select_model(candidates).name == "qwen-fast"


def test_rejects_candidate_at_two_percent_error_rate() -> None:
    with pytest.raises(NoQualifiedModelError):
        select_model(
            [
                _model(
                    "borderline",
                    cost=0.001,
                    fact_error_rate=0.02,
                    risk_recall=0.99,
                )
            ]
        )
