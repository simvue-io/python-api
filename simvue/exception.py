"""Simvue Exception Types.

Custom exceptions for handling of Simvue request scenarios.

"""


class ObjectNotFoundError(Exception):
    """For failure retrieving Simvue object from server."""

    def __init__(self, obj_type: str, name: str, extra: str | None = None) -> None:
        _msg: str = (
            f"Failed to retrieve '{name}' of type '{obj_type}' "
            f"{f'{extra}, ' if extra else ''}"
            "no such object"
        )
        super().__init__(_msg)


class SimvueRunError(RuntimeError):
    """A special sub-class of runtime error specifically for Simvue run errors."""
