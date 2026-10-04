"""What can go wrong talking to FireFly (pure). The adapter raises these; core reads them."""


class FireflyError(Exception):
    """A FireFly call failed. The message carries FireFly's own error text."""


class Reverted(FireflyError):
    """The contract refused the call (a revert). `reason` is the contract's own message."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class OperationFailed(FireflyError):
    def __init__(self, operation_id: str, error: str | None) -> None:
        super().__init__(f"operation {operation_id} failed: {error or 'no error text'}")
        self.operation_id = operation_id
        self.error = error


class OperationTimeout(FireflyError):
    def __init__(self, operation_id: str, status: str, timeout: float) -> None:
        super().__init__(f"operation {operation_id} is still {status} after {timeout:g}s")
        self.operation_id = operation_id
        self.status = status


class AlreadySubmitted(FireflyError):
    """The idempotency key was used before: the write was accepted earlier, not repeated."""

    def __init__(self, transaction_id: str) -> None:
        super().__init__(f"already submitted as transaction {transaction_id}")
        self.transaction_id = transaction_id
