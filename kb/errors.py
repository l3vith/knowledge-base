"""Structured errors rendered as {"request_id", "error": {...}} by kb/api.py."""


class KBError(Exception):
    def __init__(self, code: str, message: str, http_status: int, retryable: bool = False, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        self.details = details or {}

    def to_body(self, request_id: str) -> dict:
        return {"request_id": request_id, "error": {"code": self.code, "message": self.message,
                                                     "retryable": self.retryable, "details": self.details}}


class CollectionNotFound(KBError):
    def __init__(self, name: str):
        super().__init__("COLLECTION_NOT_FOUND", f"Collection '{name}' has no active generation.", 404,
                         details={"collection_name": name})
