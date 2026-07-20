from fruit_agent.common.redaction import redact


def redact_prompt(prompt: dict[str, object]) -> dict[str, object]:
    redacted = redact(prompt)
    if not isinstance(redacted, dict):
        raise TypeError("model prompt must be an object")
    return redacted
