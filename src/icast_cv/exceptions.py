"""Custom exception hierarchy."""


class ICastError(Exception):
    """Base exception for all ICast CV errors."""


class CameraError(ICastError):
    """Raised when a camera operation fails."""


class StorageError(ICastError):
    """Raised when a filesystem storage operation fails."""


class NotFoundError(ICastError):
    """Raised when a requested resource does not exist."""
