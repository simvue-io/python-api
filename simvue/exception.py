"""
Simvue Exception Types
======================

Custom exceptions for handling of Simvue request scenarions.

"""


class ObjectNotFoundError(Exception):
    """For failure retrieving Simvue object from server"""

    def __init__(self, obj_type: str, name: str) -> None:
        super().__init__(
            f"Failed to retrieve '{name}' of type '{obj_type}' " f"no such object"
        )


class SimvueRunError(RuntimeError):
    """A special sub-class of runtime error specifically for Simvue run errors"""

    pass