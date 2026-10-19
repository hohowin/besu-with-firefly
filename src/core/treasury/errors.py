"""Treasury errors (pure). Each one is a `ValueError` so callers can catch the family."""


class TreasuryError(ValueError):
    """Base of the treasury errors."""


class InvalidAmount(TreasuryError):
    """An amount that cannot be a funding request amount."""


class InvalidRate(TreasuryError):
    """A rate, or a rate table, that cannot be used."""


class FxRateMissing(TreasuryError):
    """No rate for the processing date and no default."""


class AmountTooSmall(TreasuryError):
    """The converted amount rounds down to nothing."""


class InvalidTransition(TreasuryError):
    """An action the request's current state does not allow."""


class InvalidReason(TreasuryError):
    """A rejection reason that is empty or too long."""


class LedgerMismatch(TreasuryError):
    """The token supplies and the requests disagree (a conservation check failed)."""
