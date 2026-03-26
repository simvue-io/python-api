"""Base Filter object for RestAPI queries."""

import abc
from collections.abc import Generator
import typing
import enum
import json
import pydantic as pyd

if typing.TYPE_CHECKING:
    from simvue.api.objects.base import SimvueObject

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035


class Time(str, enum.Enum):
    """Run stage."""

    Created = "created"
    Started = "started"
    Modified = "modified"
    Ended = "ended"


class RestAPIFilter(abc.ABC):
    """RestAPI query filter object."""

    def __init__(self, simvue_object: "type[SimvueObject] | None" = None) -> None:
        """Initialise a query object using a Simvue object class."""
        self._sv_object: "type[SimvueObject] | None" = simvue_object
        self._filters: list[str] = []
        self._generate_members()

    def _time_within(
        self, time_type: Time, *, hours: int = 0, days: int = 0, years: int = 0
    ) -> Self:
        """Define filter using time range."""
        if len(_non_zero := list(i for i in (hours, days, years) if i != 0)) > 1:
            raise AssertionError(
                "Only one duration type may be provided: hours, days or years"
            )
        if len(_non_zero) < 1:
            raise AssertionError(
                f"No duration provided for filter '{time_type.value}_within'"
            )

        if hours:
            self._filters.append(f"{time_type.value} < {hours}h")
        elif days:
            self._filters.append(f"{time_type.value} < {days}d")
        else:
            self._filters.append(f"{time_type.value} < {years}y")
        return self

    def has_name(self, name: str) -> Self:
        """Filter based on absolute object name."""
        self._filters.append(f"name == {name}")
        return self

    def has_name_containing(self, name: str) -> Self:
        """Filter base on object name containing a term."""
        self._filters.append(f"name contains {name}")
        return self

    def exclude_name(self, name: str) -> Self:
        """Veto by object name."""
        self._filters.append(f"name != {name}")
        return self

    def created_within(self, *, hours: int = 0, days: int = 0, years: int = 0) -> Self:
        """Find objects created within the last specified time period."""
        return self._time_within(Time.Created, hours=hours, days=days, years=years)

    def has_description_containing(self, search_str: str) -> Self:
        """Return objects containing the specified term within the description."""
        self._filters.append(f"description contains {search_str}")
        return self

    def exclude_description_containing(self, search_str: str) -> Self:
        """Find objects not containing the specified term in their description."""
        self._filters.append(f"description not contains {search_str}")
        return self

    def has_tag(self, tag: str) -> Self:
        """Find objects with the given tag."""
        self._filters.append(f"has tag.{tag}")
        return self

    def starred(self) -> Self:
        self._filters.append("starred")
        return self

    def as_list(self) -> list[str]:
        """Returns the filters as a list."""
        return self._filters

    def clear(self) -> None:
        """Clear all current filters."""
        self._filters = []

    def get(
        self,
        count: pyd.PositiveInt | None = None,
        offset: pyd.NonNegativeInt | None = None,
        **kwargs,
    ) -> Generator[tuple[str, "SimvueObject | None"]]:
        """Call the get method from the simvue object class."""
        if not self._sv_object:
            raise RuntimeError("No object type associated with filter.")
        _filters: str = json.dumps(self._filters)
        return self._sv_object.get(
            count=count, offset=offset, filters=_filters, **kwargs
        )

    def count(self, **kwargs) -> int:
        """Return object count."""
        if not self._sv_object:
            raise RuntimeError("No object type associated with filter.")
        _ = kwargs.pop("count", None)
        _filters: str = json.dumps(self._filters)
        return self._sv_object.count(filters=_filters, **kwargs)
