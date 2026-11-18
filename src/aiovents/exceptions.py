"""Errors raised by the Vents client."""


class VentsError(Exception):
    """Base error for the Vents protocol."""


class VentsConnectionError(VentsError):
    """The device could not be reached or did not reply."""


class VentsValueError(VentsError, ValueError):
    """A device credential, register or write value is invalid."""
