from fruit_agent.common.redaction import redact


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
