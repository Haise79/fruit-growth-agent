import pytest

from fruit_agent.common.redaction import REDACTED, redact, redact_text
from fruit_agent.copilot.safety import classify_customer_message
from fruit_agent.copilot.schemas import CopilotRisk


def test_free_text_redacts_address_landline_card_passport_and_existing_pii() -> None:
    message = (
        "寄到上海市浦东新区世纪大道100号，"
        "座机021-58881234，银行卡6222021234567890123，"
        "护照E12345678，手机13800138000，"
        "邮箱buyer@example.com，身份证310101199001011234"
    )

    result = redact_text(message)

    for sensitive in (
        "上海市浦东新区世纪大道100号",
        "021-58881234",
        "6222021234567890123",
        "E12345678",
        "13800138000",
        "buyer@example.com",
        "310101199001011234",
    ):
        assert sensitive not in result
    assert result.count(REDACTED) >= 7


@pytest.mark.parametrize("punctuation", ["。", "！", "？", "!", "?"])
def test_unlabeled_address_redaction_stops_at_sentence_punctuation(
    punctuation: str,
) -> None:
    result = redact_text(
        f"寄到上海市浦东新区世纪大道100号{punctuation}苹果发霉了"
    )

    assert "上海市浦东新区世纪大道100号" not in result
    assert f"{punctuation}苹果发霉了" in result


def test_address_redaction_preserves_following_food_safety_handoff_clause() -> None:
    redacted = redact_text("送到家。苹果发霉了")
    classification = classify_customer_message(redacted)

    assert redacted == "送到家。苹果发霉了"
    assert classification.risk is CopilotRisk.critical
    assert classification.requires_handoff is True


def test_redact_replaces_sensitive_values_recursively() -> None:
    payload = {
        "phone": "13800138000",
        "profile": {
            "address": "上海市浦东新区",
            "name": "张三",
            "contacts": [{"receiver_phone": "13900139000"}],
        },
    }

    assert redact(payload) == {
        "phone": "[REDACTED]",
        "profile": {
            "address": "[REDACTED]",
            "name": "张三",
            "contacts": [{"receiver_phone": "[REDACTED]"}],
        },
    }


def test_redact_does_not_mutate_input() -> None:
    payload = {"shipping_address": "北京市朝阳区"}

    redacted = redact(payload)

    assert redacted == {"shipping_address": "[REDACTED]"}
    assert payload == {"shipping_address": "北京市朝阳区"}
