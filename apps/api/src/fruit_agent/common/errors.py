from typing import Any


class DomainError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_content(
    *,
    code: str,
    message: str,
    request_id: str,
    details: object,
) -> dict[str, dict[str, object]]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details,
        }
    }
