"""
Simvue Exception Types
======================

Custom exceptions for handling of Simvue request scenarions.

"""

from re import Pattern


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


class SimvueFilterError(ValueError):
    """A special exception associated with filtering of objects."""

    def __init__(
        self,
        *,
        target_variable: str,
        comparator: str | None = None,
        value: str | int | float | None = None,
        permitted_comparators: list[str] | None = None,
        permitted_value_types: list[type] | None = None,
        permitted_values: list[str | int | float | None | Pattern[str]] | None = None,
    ) -> None:
        _filter: str = f"{target_variable}"
        if comparator:
            _filter += f" {comparator}"
        if value:
            _filter += f" {value}"
        _msg: str = f"Invalid filter definition '{_filter}'"

        if comparator:
            if not permitted_comparators:
                _msg += f"\nNo comparators defined for variable '{target_variable}'"
            elif comparator not in permitted_comparators or []:
                _msg += (
                    f"\nPermitted comparators are: {','.join(permitted_comparators)}"
                )
        if value:
            if permitted_value_types and type(value) not in permitted_value_types:
                _msg += f"\nInvalid type '{type(value)}' for filter value."
                _msg += f"\nPermitted types are: {','.join(str(t) for t in permitted_value_types)}"
            if permitted_values and value not in permitted_values:
                _msg += f"\nInvalid value '{value}' for filter."
                _msg += f"\nPermitted values are {','.join(str(p) for p in permitted_values)}"
        super().__init__(_msg)
