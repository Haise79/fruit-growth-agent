import re
from collections.abc import Mapping, Sequence

SENSITIVE_KEYS = {
    "phone",
    "mobile",
    "address",
    "shipping_address",
    "receiver_phone",
    "customer_name",
    "recipient_name",
    "receiver_name",
    "consignee_name",
    "wechat",
    "wechat_id",
    "weixin",
    "weixin_id",
    "qq",
    "qq_id",
    "alipay",
    "alipay_account",
    "payment_account",
    "social_handle",
    "微信号",
    "微信账号",
    "支付宝账号",
    "客户姓名",
}
_NORMALIZED_SENSITIVE_KEYS = {
    "".join(character for character in key.casefold() if character.isalnum())
    for key in SENSITIVE_KEYS
}
REDACTED = "[REDACTED]"
PII_PLACEHOLDER = "[REDACTED: PII]"
_TEXT_PATTERNS = (
    re.compile(
        r"(?i)\bqq\b(?:\s*(?:id|number|account))?"
        r"\s*(?:(?:is)|[:=：]|是|为)?\s*[1-9]\d{4,11}"
    ),
    re.compile(
        r"(?i)(?:alipay(?:\s*(?:account|id|handle))?|支付宝(?:账号|账户)?)"
        r"\s*(?:(?:is)|[:=：]|是|为)?\s*"
        r"[A-Za-z0-9][A-Za-z0-9_.@+-]{2,63}"
    ),
    re.compile(
        r"(?i)(?:wechat(?:\s*(?:id|account|handle))?|weixin(?:\s*id)?|"
        r"微信(?:号|账号)?)\s*(?:(?:is)|[:=：]|是|为)?\s*"
        r"(?:wxid_)?[A-Za-z0-9_-]{5,64}"
    ),
    re.compile(
        r"(?i)(?:customer[\s_-]*name|客户姓名)"
        r"\s*(?:(?:is)|[:=：]|是|为)?\s*"
        r"(?:[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,3}|"
        r"[\u4e00-\u9fff·]{2,20})"
    ),
    re.compile(
        r"(?i)\b(?:ship(?:ping)?\s+to|deliver(?:y)?\s+to|mail\s+to|"
        r"address)\s*[:#=-]?\s*"
        r"\d{1,6}\s+[A-Za-z0-9.' -]{1,60}"
        r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|"
        r"drive|dr|court|ct|way)\b[^\n;.!?]{0,80}"
    ),
    re.compile(
        r"(?i)\b\d{1,6}\s+[A-Za-z0-9.' -]{1,60}"
        r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|"
        r"drive|dr|court|ct|way)\b"
        r"(?:\s*,\s*[A-Za-z.' -]{2,40})?"
        r"(?:\s*,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?"
    ),
    re.compile(
        r"(?i)(?:wechat|weixin|微信)"
        r"(?:[\s_-]*(?:id|号|账号|帳號))?\s*[:：=_-]?\s*"
        r"(?:wxid_)?[A-Za-z0-9_-]{5,64}"
    ),
    re.compile(r"(?i)(?:\bqq\b|QQ号|扣扣号)\s*[:：=_-]?\s*[1-9]\d{4,11}"),
    re.compile(
        r"(?i)(?:alipay(?:[\s_-]*(?:account|id|handle))?|"
        r"支付宝(?:账号|账户)?|payment[\s_-]*(?:account|handle)|"
        r"social[\s_-]*(?:account|handle))"
        r"\s*[:：=_-]?\s*[A-Za-z0-9][A-Za-z0-9_.@+-]{2,63}"
    ),
    re.compile(
        r"(?i)(?P<label>customer[\s_-]*name|recipient[\s_-]*name|"
        r"receiver[\s_-]*name|consignee[\s_-]*name|"
        r"客户姓名|顾客姓名|收件人姓名)"
        r"\s*[:：=_-]?\s*"
        r"(?:[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,3}|"
        r"[\u4e00-\u9fff·]{2,20})"
    ),
    re.compile(
        r"(?P<prefix>寄到|送到|邮寄到|配送到|"
        r"收货地(?:址)?(?:是|为)?)\s*"
        r"(?:[^,，;；。！？!?\n]{0,24}?"
        r"(?:省|市|区|县|路|街|道|巷|号|栋|单元|室))+"
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

_RESIDUAL_PII_PATTERNS = (
    *_TEXT_PATTERNS,
    re.compile(r"(?i)(?<![A-Za-z0-9_])wxid_[A-Za-z0-9_-]{5,64}(?![A-Za-z0-9_])"),
)


def contains_supported_pii(value: str) -> bool:
    sanitized = value.replace(PII_PLACEHOLDER, "").replace(REDACTED, "")
    return any(
        pattern.search(sanitized) is not None
        for pattern in _RESIDUAL_PII_PATTERNS
    )


def _normalize_sensitive_key(key: object) -> str:
    return "".join(
        character
        for character in str(key).casefold()
        if character.isalnum()
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
        redacted = redact_text(value)
        return PII_PLACEHOLDER if contains_supported_pii(redacted) else redacted
    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED
                if _normalize_sensitive_key(key) in _NORMALIZED_SENSITIVE_KEYS
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
