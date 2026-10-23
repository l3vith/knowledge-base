class QueryError(RuntimeError):
    def __init__(self, code, message, http_status=500, retryable=False):
        super().__init__(message)
        self.code, self.message = code, message
        self.http_status, self.retryable = http_status, retryable

    def to_body(self, request_id):
        return {"request_id": request_id, "error": {"code": self.code, "message": self.message,
                                                     "retryable": self.retryable}}


class BudgetExceeded(QueryError):
    def __init__(self, reason):
        super().__init__("QUERY_BUDGET", reason, 504)
