from collections.abc import Mapping, Sequence

SENSITIVE_KEYS = {
    "phone",
    "mobile",
    "address",
    "shipping_address",
    "receiver_phone",
}
REDACTED = "[REDACTED]"


def redact(value: object) -> object:
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
