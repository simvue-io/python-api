"""Simvue RestAPI Runs Filter."""

import enum
import typing

from .base import RestAPIFilter, Time

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035

Status = typing.Literal[
    "lost", "failed", "completed", "terminated", "running", "created"
]


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


class RunsFilter(RestAPIFilter):
    """Filter for searching runs on the Simvue server."""

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

                def _out_func(value: str | int | float, func=function) -> Self:
                    return func("system", system_spec.value, value)

                _out_func.__name__ = _func_name
                setattr(self, _func_name, _out_func)

        for function in _global_comparators + _numeric_comparators:
            _func_name = function.__name__.replace("_value", "metadata")

            def _out_func(
                attribute: str, value: str | int | float, func=function
            ) -> Self:
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
        self._filters.append(f"status == {status}")
        return self

    def is_running(self) -> "RunsFilter":
        """Filter by if run is running."""
        return self.has_status("running")

    def is_lost(self) -> "RunsFilter":
        """Filter by if run is lost."""
        return self.has_status("lost")

    def has_completed(self) -> "RunsFilter":
        """Filter by if run has completed."""
        return self.has_status("completed")

    def has_failed(self) -> "RunsFilter":
        """Filter by if run has failed."""
        return self.has_status("failed")

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
        self, category: str, attribute: str, value: str | int | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} == {value}")
        return self

    def _value_neq(
        self, category: str, attribute: str, value: str | int | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} != {value}")
        return self

    def _value_contains(
        self, category: str, attribute: str, value: str | int | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} contains {value}")
        return self

    def _value_leq(
        self, category: str, attribute: str, value: int | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} <= {value}")
        return self

    def _value_geq(
        self, category: str, attribute: str, value: int | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} >= {value}")
        return self

    def _value_lt(
        self, category: str, attribute: str, value: int | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} < {value}")
        return self

    def _value_gt(
        self, category: str, attribute: str, value: int | float
    ) -> "RunsFilter":
        self._filters.append(f"{category}.{attribute} > {value}")
        return self

    def __str__(self) -> str:
        return " && ".join(self._filters) if self._filters else "None"

    def __repr__(self) -> str:
        return f"{super().__repr__()[:-1]}, filters={self._filters}>"
