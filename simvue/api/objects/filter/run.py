"""Simvue RestAPI Runs Filter."""

import typing
import semver

from .base import RestAPIFilter, Time

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035

Status = typing.Literal[
    "lost", "failed", "completed", "terminated", "running", "created"
]


class RunsFilter(RestAPIFilter):
    """Filter for searching runs on the Simvue server."""

    def has_name(self, name: str) -> "RunsFilter":
        """Filter based on absolute object name."""
        self._filters.append(f"name == {name}")
        return self

    def has_name_containing(self, name: str) -> "RunsFilter":
        """Filter base on object name containing a term."""
        self._filters.append(f"name contains {name}")
        return self

    def exclude_name(self, name: str) -> "RunsFilter":
        """Veto by object name."""
        self._filters.append(f"name != {name}")
        return self

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

    def in_folder_containing(self, folder_name: str) -> "RunsFilter":
        """Filter by whether run is in folder path with expression."""
        self._filters.append(f"folder.path contains {folder_name}")
        return self

    def exclude_in_folder(self, folder_name: str) -> "RunsFilter":
        """Filter by whether run is not within the given folder."""
        self._filters.append(f"folder.path != {folder_name}")
        return self

    def has_working_directory(self, working_dir: str) -> "RunsFilter":
        """Filter by whether run was executed in a given directory."""
        self._filters.append(f"system.cwd == {working_dir}")
        return self

    def exclude_working_directory(self, working_dir: str) -> "RunsFilter":
        """Veto by whether run was executed in a given directory."""
        self._filters.append(f"system.cwd != {working_dir}")
        return self

    def has_hostname(self, hostname: str) -> "RunsFilter":
        """Filter by simulation host machine."""
        self._filters.append(f"system.hostname == {hostname}")
        return self

    def exclude_hostname(self, hostname: str) -> "RunsFilter":
        """Veto by simulation host machine."""
        self._filters.append(f"system.hostname != {hostname}")
        return self

    def has_cpu(
        self, *, architecture: str | None = None, processor: str | None = None
    ) -> "RunsFilter":
        """Filter by CPU architecture and processor."""
        if architecture:
            self._filters.append(f"system.cpu.arch == {architecture}")
        if processor:
            self._filters.append(f"system.cpu.processor == {processor}")
        return self

    def exclude_cpu(
        self, *, architecture: str | None = None, processor: str | None = None
    ) -> "RunsFilter":
        """Veto by CPU architecture and processor."""
        if architecture:
            self._filters.append(f"system.cpu.arch != {architecture}")
        if processor:
            self._filters.append(f"system.cpu.processor != {processor}")
        return self

    def has_gpu(
        self, *, name: str | None = None, processor: str | None = None
    ) -> "RunsFilter":
        """Filter by GPU name or processor.

        If no arguments are given this filters by runs which are on a
        system which has GPU capability.
        """
        if name:
            self._filters.append(f"system.gpu.name == {name}")
        if processor:
            self._filters.append(f"system.gpu.processor == {name}")
        return self

    def exclude_gpu(
        self, *, name: str | None = None, processor: str | None = None
    ) -> "RunsFilter":
        """Veto by GPU name or processor."""
        if name:
            self._filters.append(f"system.gpu.name != {name}")
        if processor:
            self._filters.append(f"system.gpu.processor != {name}")
        return self

    def has_python_version(self, python_version: str) -> "RunsFilter":
        try:
            _ = semver.Version.parse(python_version)
        except ValueError as e:
            raise ValueError(
                f"'{python_version}' is not a valid semantic version."
            ) from e
        self._filters.append(f"system.pythonversion == {python_version}")
        return self

    def exclude_python_version(self, python_version: str) -> "RunsFilter":
        try:
            _ = semver.Version.parse(python_version)
        except ValueError as e:
            raise ValueError(
                f"'{python_version}' is not a valid semantic version."
            ) from e
        self._filters.append(f"system.pythonversion != {python_version}")
        return self

    def has_platform(
        self, platform: str, *, release: str | None = None, version: str | None = None
    ) -> "RunsFilter":
        """Filter by simulation host platform."""
        self._filters.append(f"system.platform.system == {platform}")
        if release:
            self._filters.append(f"system.platform.release == {release}")
        if version:
            self._filters.append(f"system.platform.version == {version}")
        return self

    def exclude_platform(
        self, platform: str, *, release: str | None = None, version: str | None = None
    ) -> "RunsFilter":
        """Veto by simulation host platform.

        If platform is specified then results WITHOUT this platform are returned.
        However if a version and/or release is given then results WITH the given platform
        but NOT the given release/version are returned.
        """
        self._filters.append(
            "system.platform.system " + "!="
            if not release and not version
            else "==" + " " + platform
        )
        if release:
            self._filters.append(f"system.platform.release != {release}")
        if version:
            self._filters.append(f"system.platform.version != {version}")
        return self

    @override
    def __str__(self) -> str:
        return " && ".join(self._filters) if self._filters else "None"

    @override
    def __repr__(self) -> str:
        return f"{super().__repr__()[:-1]}, filters={self._filters}>"
