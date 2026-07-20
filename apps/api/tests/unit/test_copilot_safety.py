import pytest

from fruit_agent.copilot.safety import classify_customer_message, merge_model_risk
from fruit_agent.copilot.schemas import CopilotIntent, CopilotRisk, CopilotStage


def test_health_allergy_or_disease_requires_handoff() -> None:
    result = classify_customer_message("孩子有苹果过敏和糖尿病，可以吃这个吗？")

    assert result.stage is CopilotStage.presale
    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_food_safety_concern_requires_handoff() -> None:
    result = classify_customer_message("苹果有异味，吃起来像变质了，安全吗？")

    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_bulk_spoilage_or_public_opinion_threat_requires_handoff() -> None:
    result = classify_customer_message("整批礼盒都发霉了，不处理我就发到微博曝光")

    assert result.stage is CopilotStage.aftersale
    assert result.risk is CopilotRisk.high
    assert result.requires_handoff is True


def test_bulk_spoilage_without_public_threat_requires_handoff() -> None:
    result = classify_customer_message("客户反馈五十箱苹果整批腐烂")

    assert result.risk is CopilotRisk.high
    assert result.requires_handoff is True


def test_public_opinion_threat_without_bulk_spoilage_requires_handoff() -> None:
    result = classify_customer_message("不处理我就找媒体曝光并送上热搜")

    assert result.intent is CopilotIntent.complaint
    assert result.risk is CopilotRisk.high
    assert result.requires_handoff is True


def test_regulator_complaint_requires_handoff() -> None:
    result = classify_customer_message("我要向市场监管局和消协投诉你们")

    assert result.intent is CopilotIntent.complaint
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_over_policy_compensation_or_refund_dispute_requires_handoff() -> None:
    result = classify_customer_message("你们的退款方案我不同意，必须十倍赔偿")

    assert result.intent is CopilotIntent.refund
    assert result.risk is CopilotRisk.high
    assert result.requires_handoff is True


def test_personal_injury_requires_handoff() -> None:
    result = classify_customer_message("吃完后摔倒受伤住院了，医药费怎么办")

    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_knowledge_conflict_requires_handoff() -> None:
    result = classify_customer_message(
        "这款苹果多少钱？",
        knowledge_conflict=True,
    )

    assert result.risk is CopilotRisk.high
    assert result.requires_handoff is True


def test_asthma_question_requires_handoff() -> None:
    result = classify_customer_message("我有哮喘，可以吃吗？")

    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_adverse_digestive_symptoms_require_handoff() -> None:
    result = classify_customer_message("吃完后一直腹泻呕吐")

    assert result.stage is CopilotStage.aftersale
    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_industry_regulator_complaint_requires_handoff() -> None:
    result = classify_customer_message("我要去工商局投诉")

    assert result.intent is CopilotIntent.complaint
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_english_asthma_question_requires_handoff() -> None:
    result = classify_customer_message("I have asthma; can I eat this?")

    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


def test_english_adverse_digestive_reaction_requires_handoff() -> None:
    result = classify_customer_message(
        "I have diarrhea and vomiting after eating these"
    )

    assert result.stage is CopilotStage.aftersale
    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


@pytest.mark.parametrize(
    "message",
    [
        "I have chronic kidney disease. Is this safe to eat?",
        "Can someone with heart disease or an immune disorder eat this?",
        "I developed nausea and stomach pain after eating the fruit.",
        "After eating these I have a fever, dizziness, and a rash.",
        "My throat is swelling and I have difficulty breathing.",
    ],
)
def test_common_english_disease_and_adverse_reaction_variants_fail_closed(
    message: str,
) -> None:
    result = classify_customer_message(message)

    assert result.risk in {CopilotRisk.high, CopilotRisk.critical}
    assert result.requires_handoff is True


@pytest.mark.parametrize(
    "message",
    [
        "我有心脏病和慢性肾病，能吃这种水果吗",
        "免疫系统疾病患者能不能吃",
        "吃了以后持续恶心肚子痛",
        "收到后吃了发烧头晕",
        "我要打12345消费者热线投诉",
        "我会向消费者协会举报",
    ],
)
def test_common_health_symptom_and_consumer_regulator_variants_fail_closed(
    message: str,
) -> None:
    result = classify_customer_message(message)

    assert result.risk in {CopilotRisk.high, CopilotRisk.critical}
    assert result.requires_handoff is True


@pytest.mark.parametrize(
    "message",
    [
        "My child has an apple allergy and diabetes. Is it safe?",
        "These apples smell rotten and may cause food poisoning.",
        "Fifty boxes arrived spoiled.",
        "I will report this to the market regulator.",
        "I reject the refund offer and demand compensation above policy.",
        "I was injured and hospitalized after eating this.",
    ],
)
def test_english_mandatory_risk_language_requires_handoff(message: str) -> None:
    result = classify_customer_message(message)

    assert result.risk in {CopilotRisk.high, CopilotRisk.critical}
    assert result.requires_handoff is True


@pytest.mark.parametrize(
    "message",
    [
        "She is in anaphylactic shock after eating the apple.",
        "He stopped breathing after consuming the fruit.",
        "The customer is unconscious; call an ambulance.",
        "My father died after consuming this product.",
        "I have severe swelling after eating these apples.",
        "She collapsed after eating the apple.",
        "He is unresponsive after consuming the fruit.",
        "The customer couldn't breathe after eating it.",
        "食用后倒地无反应。",
        "吃完苹果后已经没有呼吸了，请叫救护车。",
        "顾客食用后失去意识，出现严重肿胀。",
    ],
)
def test_severe_post_consumption_health_language_requires_handoff(
    message: str,
) -> None:
    result = classify_customer_message(message)

    assert result.stage is CopilotStage.aftersale
    assert result.intent is CopilotIntent.health_safety
    assert result.risk is CopilotRisk.critical
    assert result.requires_handoff is True


@pytest.mark.parametrize(
    ("rule_risk", "model_risk", "expected"),
    [
        (CopilotRisk.low, CopilotRisk.medium, CopilotRisk.medium),
        (CopilotRisk.medium, CopilotRisk.low, CopilotRisk.medium),
        (CopilotRisk.high, CopilotRisk.critical, CopilotRisk.critical),
    ],
)
def test_model_risk_can_upgrade_but_never_downgrade(
    rule_risk: CopilotRisk,
    model_risk: CopilotRisk,
    expected: CopilotRisk,
) -> None:
    assert merge_model_risk(rule_risk, model_risk) is expected
