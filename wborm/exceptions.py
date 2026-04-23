"""WBORM exception hierarchy."""


class ORMError(Exception):
    """Base exception for WBORM."""


class ORMValidationError(ValueError, ORMError):
    """Entity validation failed."""


class ORMConcurrencyError(RuntimeError, ORMError):
    """Optimistic or pessimistic concurrency violation."""


class ORMDatabaseError(RuntimeError, ORMError):
    """Database execution failed."""
