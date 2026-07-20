from fruit_agent.common.redaction import REDACTED, redact
from fruit_agent.model_gateway.redaction import redact_prompt


def test_sensitive_fields_never_reach_model_or_audit_payloads() -> None:
    payload: dict[str, object] = {
        "message": "查询订单",
        "phone": "13800138000",
        "customer": {
            "shipping_address": "上海市浦东新区",
            "name": "张三",
        },
    }

    model_prompt = redact_prompt(payload)
    audit_payload = redact(payload)

    assert model_prompt["phone"] == REDACTED
    customer = model_prompt["customer"]
    assert isinstance(customer, dict)
    assert customer["shipping_address"] == REDACTED
    assert audit_payload == model_prompt
    assert "13800138000" not in repr(model_prompt)
    assert "上海市浦东新区" not in repr(model_prompt)
