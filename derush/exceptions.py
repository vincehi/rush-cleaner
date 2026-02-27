"""Custom exceptions for the derush package."""


class DerushError(Exception):
    """Base exception for derush package."""

    pass


class TranscriptionError(DerushError):
    """Raised when transcription fails."""

    pass


class MediaInfoError(DerushError):
    """Raised when media info cannot be extracted."""

    pass


class ExportError(DerushError):
    """Raised when export fails."""

    pass


class ValidationError(DerushError):
    """Raised when input validation fails."""

    pass
