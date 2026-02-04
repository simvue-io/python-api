"""
Simvue Exception Types
======================

Custom exceptions for handling of Simvue request scenarions.

"""


class ObjectNotFoundError(Exception):
    """For failure retrieving Simvue object from server"""

    def __init__(self, obj_type: str, name: str, extra: str | None = None) -> None:
        super().__init__(
            f"Failed to retrieve '{name}' of type '{obj_type}' "
            f"{f'{extra}, ' if extra else ''}"
            "no such object"
        )


class SimvueRunError(RuntimeError):
    """A special sub-class of runtime error specifically for Simvue run errors"""


class ObjectDispatchError(Exception):
    """Raised if object dispatch failed due to condition."""

    def __init__(self, label: str, threshold: int | float, value: int | float) -> None:
        self.msg = (
            f"Object dispatch failed, {label} "
            + f"of {value} exceeds maximum permitted value of {threshold}"
        )
        super().__init__(self.msg)
