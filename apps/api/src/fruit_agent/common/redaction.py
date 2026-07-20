import re
from collections.abc import Mapping, Sequence

SENSITIVE_KEYS = {
    "phone",
    "mobile",
    "address",
    "shipping_address",
    "receiver_phone",
}
REDACTED = "[REDACTED]"
_TEXT_PATTERNS = (
    re.compile(
        r"(?P<prefix>寄到|送到|邮寄到|配送到|"
        r"收货地(?:址)?(?:是|为)?|地址(?:是|为)?)"
        r"\s*[^,，;；。！？!?\n]{1,80}"
    ),
    re.compile(
        r"(?P<label>收货地址|地址|姓名|收件人)"
        r"\s*[:：]\s*[^,，;；。！？!?\n]+"
    ),
    re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])"),
    re.compile(
        r"(?i)(?:passport|护照(?:号|号码)?)"
        r"\s*[:：]?\s*[A-Z0-9]{6,12}"
    ),
    re.compile(r"(?<![A-Za-z0-9])[EeGgDdPpHhSs]\d{8}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){15,18}\d(?!\d)"),
    re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)0\d{2,3}[- ]?\d{7,8}(?!\d)"),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in _TEXT_PATTERNS:
        if "prefix" in pattern.groupindex:
            redacted = pattern.sub(
                lambda match: f"{match.group('prefix')}{REDACTED}",
                redacted,
            )
        elif "label" in pattern.groupindex:
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
