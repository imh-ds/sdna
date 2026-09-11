"""Package-specific exceptions."""


class SDNAError(Exception):
    """Base exception for SDNA errors."""


class CalibrationError(SDNAError):
    """Raised when calibration cannot construct a valid reference model."""
