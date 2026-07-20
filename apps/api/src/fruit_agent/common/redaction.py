from collections.abc import Mapping, Sequence
import re

SENSITIVE_KEYS = {
    "phone",
    "mobile",
    "address",
    "shipping_address",
    "receiver_phone",
}
REDACTED = "[REDACTED]"
_TEXT_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"(?P<label>收货地址|地址|姓名|收件人)\s*[:：]\s*[^,，;；\n]+"),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in _TEXT_PATTERNS:
        if "label" in pattern.groupindex:
            redacted = pattern.sub(
                lambda match: f"{match.group('label')}：{REDACTED}",
                redacted,
            )
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact(value: object) -> object:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED
                if str(key).lower() in SENSITIVE_KEYS
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [redact(item) for item in value]
    return value
