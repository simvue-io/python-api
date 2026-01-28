"""
Simvue Exception Types
======================

Custom exceptions for handling of Simvue request scenarions.

"""


class SimvueException(Exception):
    """Base exception for all Simvue Python API errors."""

    pass


class ObjectNotFoundError(SimvueException):
    """For failure retrieving Simvue object from server"""

    def __init__(self, obj_type: str, name: str, extra: str | None = None) -> None:
        super().__init__(
            f"Failed to retrieve '{name}' of type '{obj_type}' "
            f"{f'{extra}, ' if extra else ''}"
            "no such object"
        )


class SimvueRunError(SimvueException, RuntimeError):
    """A special sub-class of runtime error specifically for Simvue run errors"""

    pass


class SimvueUserConfigError(SimvueException):
    """Raised when no local Simvue Configuration file has been found."""

    pass
