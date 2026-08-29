class FpvDroneError(Exception):
    """Base error with a concise user-facing message."""


class ValidationError(FpvDroneError):
    """Input catalog or recipe is invalid."""


class ResolutionError(FpvDroneError):
    """A recipe reference cannot be resolved."""
