from __future__ import annotations


class APIKeyMissingError(Exception):
    """Exception raised when an API key is missing or invalid."""


class InvalidResponseError(Exception):
    """Exception raised when an API response is invalid or malformed."""


class DistanceMatrixRequestError(Exception):
    """Exception raised when distance matrix request fails."""


class SolverError(Exception):
    """Exception raised when the VRP solver encounters an error."""


class AppError(Exception):
    """Base app error."""


class DistanceMatrixRequestError(AppError):
    """Raised when a distance-matrix provider fails."""


class SolverRequestError(AppError):
    """Raised when a VRP solver fails or is misconfigured."""
