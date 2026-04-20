"""Simvue Object Filters.

Provides an interface for the creation and use of filters when retrieving
objects from the Simvue server.
"""

import abc
import enum
import json
import typing
from collections.abc import Generator

import pydantic

try:
    from typing import Self
except ImportError:
    from typing import Self


if typing.TYPE_CHECKING:
    from .base import SimvueObject


class Status(str, enum.Enum):
    """Status of run."""

    Created = "created"
    Running = "running"
    Completed = "completed"
    Lost = "lost"
    Terminated = "terminated"
    Failed = "failed"


class Time(str, enum.Enum):
    """Run stage."""

    Created = "created"
    Started = "started"
    Modified = "modified"
    Ended = "ended"


class System(str, enum.Enum):
    """System metadata filtering."""

    Working_Directory = "cwd"
    Hostname = "hostname"
    Python_Version = "pythonversion"
    Platform_System = "platform.system"
    Platform_Release = "platform.release"
    Platform_Version = "platform.version"
    CPU_Architecture = "cpu.arch"
    CPU_Processor = "cpu.processor"
    GPU_Name = "gpu.name"
    GPU_Driver = "gpu.driver"


class RestAPIFilter(abc.ABC):
    """RestAPI query filter object."""

    def __init__(self, simvue_object: "type[SimvueObject] | None" = None) -> None:
        """Initialise a query object using a Simvue object class."""
        self._sv_object: type[SimvueObject] | None = simvue_object
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

    @abc.abstractmethod
    def _generate_members(self) -> None:
        """Generate filters using specified definitions."""

    def has_name(self, name: str) -> Self:
        """Filter based on absolute object name."""
        self._filters.append(f"name == {name}")
        return self

    def has_name_containing(self, name: str) -> Self:
        """Filter base on object name containing a term."""
        self._filters.append(f"name contains {name}")
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
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.NonNegativeInt | None = None,
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


class FoldersFilter(RestAPIFilter):
    """Filter for Folders."""

    def has_path(self, name: str) -> "FoldersFilter":
        """Check if a folder has the given path."""
        self._filters.append(f"path == {name}")
        return self

    def has_path_containing(self, name: str) -> "FoldersFilter":
        """Check if the folder path contains a search term."""
        self._filters.append(f"path contains {name}")
        return self

    def _generate_members(self) -> None:
        return super()._generate_members()


class RunsFilter(RestAPIFilter):
    """Filter for Runs."""

    def _generate_members(self) -> None:
        _global_comparators = [self._value_contains, self._value_eq, self._value_neq]

        _numeric_comparators = [
            self._value_geq,
            self._value_leq,
            self._value_lt,
            self._value_gt,
        ]

        for label, system_spec in System.__members__.items():
            for function in _global_comparators:
                _label: str = label.lower()
                _func_name: str = function.__name__.replace("_value", _label)

                def _out_func(value: str | float, func=function) -> Self:
                    return func("system", system_spec.value, value)

                _out_func.__name__ = _func_name
                setattr(self, _func_name, _out_func)

        for function in _global_comparators + _numeric_comparators:
            _func_name = function.__name__.replace("_value", "metadata")

            def _out_func(attribute: str, value: str | float, func=function) -> Self:
                return func("metadata", attribute, value)

            _out_func.__name__ = _func_name
            setattr(self, _func_name, _out_func)

    def owner(self, username: str = "self") -> "RunsFilter":
        """Filter by run owner."""
        self._filters.append(f"user == {username}")
        return self

    def exclude_owner(self, username: str = "self") -> "RunsFilter":
        """Veto by run owner."""
        self._filters.append(f"user != {username}")
        return self

    def has_status(self, status: Status) -> "RunsFilter":
        """Filter by run status."""
        self._filters.append(f"status == {status.value}")
        return self

    def is_running(self) -> "RunsFilter":
        """Filter by if run is running."""
        return self.has_status(Status.Running)

    def is_lost(self) -> "RunsFilter":
        """Filter by if run is lost."""
        return self.has_status(Status.Lost)

    def has_completed(self) -> "RunsFilter":
        """Filter by if run has completed."""
        return self.has_status(Status.Completed)

    def has_failed(self) -> "RunsFilter":
        """Filter by if run has failed."""
        return self.has_status(Status.Failed)

    def has_alert(
        self, alert_name: str, is_critical: bool | None = None
    ) -> "RunsFilter":
        """Filter by if run has a given alert."""
        self._filters.append(f"alert.name == {alert_name}")
        if is_critical is True:
            self._filters.append("alert.status == critical")
        elif is_critical is False:
            self._filters.append("alert.status == ok")
        return self

    def started_within(
        self, *, hours: int = 0, days: int = 0, years: int = 0
    ) -> "RunsFilter":
        """Filter by run start time interval."""
        return self._time_within(Time.Started, hours=hours, days=days, years=years)

    def modified_within(
        self, *, hours: int = 0, days: int = 0, years: int = 0
    ) -> "RunsFilter":
        """Filter by run modified time interval."""
        return self._time_within(Time.Modified, hours=hours, days=days, years=years)

    def ended_within(
        self, *, hours: int = 0, days: int = 0, years: int = 0
    ) -> "RunsFilter":
        """Filter by run end time interval."""
        return self._time_within(Time.Ended, hours=hours, days=days, years=years)

    def in_folder(self, folder_name: str) -> "RunsFilter":
        """Filter by whether run is within the given folder."""
        self._filters.append(f"folder.path == {folder_name}")
        return self

    def has_metadata_attribute(self, attribute: str) -> "RunsFilter":
        """Filter by whether run has the given metadata attribute."""
        self._filters.append(f"metadata.{attribute} exists")
        return self

    def exclude_metadata_attribute(self, attribute: str) -> "RunsFilter":
        """Veto by whether run has the given metadata attribute."""
        self._filters.append(f"metadata.{attribute} not exists")
        return self

    def _value_eq(
        self, category: str, attribute: str, value: str | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} == {value}")
        return self

    def _value_neq(
        self, category: str, attribute: str, value: str | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} != {value}")
        return self

    def _value_contains(
        self, category: str, attribute: str, value: str | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} contains {value}")
        return self

    def _value_leq(self, category: str, attribute: str, value: float) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} <= {value}")
        return self

    def _value_geq(self, category: str, attribute: str, value: float) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} >= {value}")
        return self

    def _value_lt(self, category: str, attribute: str, value: float) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} < {value}")
        return self

    def _value_gt(self, category: str, attribute: str, value: float) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} > {value}")
        return self

    def __str__(self) -> str:
        return " && ".join(self._filters) if self._filters else "None"

    def __repr__(self) -> str:
        return f"{super().__repr__()[:-1]}, filters={self._filters}>"
