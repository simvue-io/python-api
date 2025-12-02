"""Filter validation."""

from re import Pattern
import re
from typing import Any, Callable, Self, override
import pydantic

from simvue.exception import SimvueFilterError

def _check_filter(
    *,
    target_variable: str,
    comparator: str | None,
    value: str | int | float | None,
    permitted_comparators: list[str] | None = None,
    permitted_value_types: list[type] | None = None,
    permitted_values: list[str | int | float | None | Pattern[str]] | None = None,
) -> None:
    _filter_error = SimvueFilterError(
        comparator=comparator,
        target_variable=target_variable,
        value=value,
        permitted_comparators=permitted_comparators,
        permitted_value_types=permitted_value_types,
        permitted_values=permitted_values,
    )
    if comparator and permitted_comparators and comparator not in permitted_comparators:
        raise _filter_error
    if value and permitted_value_types and type(value) not in permitted_value_types:
        raise _filter_error
    if not value and None not in (permitted_values or []):
        raise _filter_error
    if permitted_values:
        if value in permitted_values:
            return
        for permitted in permitted_values:
            if isinstance(permitted, Pattern) and permitted.search(str(value)):
                return
        raise _filter_error

FILTER_TYPES: dict[Pattern[str], dict[str, list[str | type] | None]] = {
    re.compile(r"^metadata\."): {
        "permitted_comparators": ["==", "!=", "<", "<=", ">", ">=", "contains", "exists", "not exists"],
        "permitted_types": [str, int, float],
        "permitted_values": None
    },
    re.compile(r"^name$"): {
        "permitted_comparators": ["==", "contains"],
        "permitted_types": [str],
        "permitted_values": None
    }
}


class Filter(pydantic.BaseModel):
    _allowed_filters: dict[
        str,
        dict[str | None, Callable[[Any], bool]],
    ] = pydantic.PrivateAttr(default_factory=dict)
    variable: str
    operator: str | None
    value: str | None

    @pydantic.model_validator(mode="after")
    def check_valid_filter(self) -> Self:
        """Check filter is valid."""
        _run_filter_exception_args: dict[str, list[str] | None | str] = {}
        if (_meta := self.variable.startswith("metadata.")) or (
            _metric := self.variable.startswith("metrics.")
        ):
            _permitted_comparators: list[str] =
            if _meta and self.operator in ("contains", "exists", "not exists"):
                return self
            if self.operator not in ("<", "<=", ">", ">=", "==", "!="):
                raise ValueError(
                    f"Invalid operator '{self.operator}' "
                    + f"for '{'metadata' if _meta else 'metric'}' filter"
                )
            return self
        if self.variable.startswith("system."):
            if self.operator not in ("==", "!=", "contains"):
                raise SimvueFilterError(
                    f"Invalid operator '{self.operator}' for system metrics filter"
                )
        if not (_filter := self._allowed_filters.get(self.variable)):
            raise ValueError(f"'{self.variable}' is not a recognised filter.")
        try:
            _filter_validator: Callable[[Any], bool] = _filter[self.operator]
        except KeyError:
            _msg: str = f"'{self.operator}' is not a valid filter operator"
            if self.variable:
                _msg += f" for variable '{self.variable}'"
            raise ValueError(_msg)

        if not _filter_validator(self.value):
            raise ValueError(
                f"Invalid value for filter '{self.variable} {self.operator}'"
            )
        if _run_filter_exception_args:
            raise SimvueFilterError(
                target_variable=self.variable, **_run_filter_exception_args
            )
        return self

    @override
    def __str__(self) -> str:
        _out_str = self.variable
        if self.operator:
            _out_str += f" {self.operator}"
        if self.value:
            _out_str += f" {self.value}"
        return _out_str

    @classmethod
    def from_list(cls, filters: list[str]) -> list[Self]:
        _out_filters: list[Self] = []
        for filter in filters:
            _filter: list[str | None] = [None, None, None]
            _components = filter.strip().split()
            for i, component in enumerate(_components):
                _filter[i] = component.strip()
            _out_filters.append(
                cls(**dict(zip(("variable", "operator", "value"), _filter)))
            )

        return _out_filters
