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


@pytest.mark.parametrize(
    "message",
    [
        "Ship to 123 Main Street, Springfield, IL 62704",
        "WeChat ID: wxid_alice123",
        "customer_name Alice Zhang",
        "QQ: 123456789",
        "Alipay account: alice.pay",
        "My QQ is 123456789",
        "Alipay handle is alice.pay",
        "微信号是 wxid_alice123",
        "支付宝账号为 alice.pay",
        "客户姓名是 Alice Zhang",
    ],
)
def test_free_text_redacts_multilingual_address_name_and_social_handles(
    message: str,
) -> None:
    result = redact_text(message)

    assert result != message
    assert REDACTED in result
    assert not any(
        token in result
        for token in (
            "123 Main Street",
            "wxid_alice123",
            "Alice Zhang",
            "123456789",
            "alice.pay",
        )
    )


def test_redact_normalizes_structured_sensitive_key_variants() -> None:
    payload = {
        "customerName": "Alice Zhang",
        "WECHAT-ID": "wxid_alice123",
        "payment_account": "alice.pay",
        "receiver.phone": "13800138000",
        "微信号": "wxid_alice123",
        "支付宝账号": "alice.pay",
        "客户姓名": "Alice Zhang",
    }

    assert redact(payload) == {
        "customerName": REDACTED,
        "WECHAT-ID": REDACTED,
        "payment_account": REDACTED,
        "receiver.phone": REDACTED,
        "微信号": REDACTED,
        "支付宝账号": REDACTED,
        "客户姓名": REDACTED,
    }


def test_recursive_redaction_fail_closes_on_residual_pii_independently() -> None:
    payload = {
        "safe_key": {
            "notes": ["ordinary", "contact wxid_alice123"],
        }
    }

    assert redact(payload) == {
        "safe_key": {
            "notes": ["ordinary", "[REDACTED: PII]"],
        }
    }


def test_redact_does_not_mutate_input() -> None:
    payload = {"shipping_address": "北京市朝阳区"}

    redacted = redact(payload)

    assert redacted == {"shipping_address": "[REDACTED]"}
    assert payload == {"shipping_address": "北京市朝阳区"}
