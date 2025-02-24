"""
Simvue Runs
===========

Contains a class for remotely connecting to Simvue runs, or defining
a new run given relevant arguments.

"""

import http
import typing
import pydantic
import datetime
import time

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from .base import SimvueObject, staging_check, Visibility, write_only
from simvue.api.request import (
    get as sv_get,
    put as sv_put,
    get_json_from_response,
)
from simvue.api.url import URL
from simvue.models import FOLDER_REGEX, NAME_REGEX, DATETIME_FORMAT

Status = typing.Literal[
    "lost", "failed", "completed", "terminated", "running", "created"
]

__all__ = ["Run"]


class Run(SimvueObject):
    """Class for interacting with/creating runs on the server."""

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        """Initialise a Run

        If an identifier is provided a connection will be made to the
        object matching the identifier on the target server.
        Else a new Run will be created using arguments provided in kwargs.

        Parameters
        ----------
        identifier : str, optional
            the remote server unique id for the target run
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        self.visibility = Visibility(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        folder: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
        system: dict[str, typing.Any] | None = None,
        status: typing.Literal[
            "terminated", "created", "failed", "completed", "lost", "running"
        ] = "created",
        offline: bool = False,
        **kwargs,
    ) -> Self:
        """Create a new Run on the Simvue server.

        Parameters
        ----------
        folder : str
            folder to contain this run
        offline : bool, optional
            create the run in offline mode, default False.

        Returns
        -------
        Run
            run object with staged changes
        """
        return Run(
            folder=folder,
            system=system,
            status=status,
            _read_only=False,
            _offline=offline,
            **kwargs,
        )

    @property
    @staging_check
    def name(self) -> str:
        """Retrieve name associated with this run"""
        return self._get_attribute("name")

    def delete(self, **kwargs) -> dict[str, typing.Any]:
        # Any metric entries need to also be removed
        return super().delete(_linked_objects=["metrics", "events"], **kwargs)

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> None:
        """Set the name for this run."""
        self._staging["name"] = name

    @property
    @staging_check
    def tags(self) -> list[str]:
        """Retrieve the tags associated with this run."""
        return self._get_attribute("tags")

    @tags.setter
    @write_only
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        """Set the tags for this run."""
        self._staging["tags"] = tags

    @property
    @staging_check
    def status(self) -> Status:
        """Get the run status."""
        return self._get_attribute("status")

    @status.setter
    @write_only
    @pydantic.validate_call
    def status(self, status: Status) -> None:
        """Set the run status."""
        self._staging["status"] = status

    @property
    @staging_check
    def ttl(self) -> int:
        """Return the retention period for this run"""
        return self._get_attribute("ttl")

    @ttl.setter
    @write_only
    @pydantic.validate_call
    def ttl(self, time_seconds: pydantic.NonNegativeInt | None) -> None:
        """Update the retention period for this run"""
        self._staging["ttl"] = time_seconds

    @property
    @staging_check
    def folder(self) -> str:
        """Get the folder associated with this run."""
        return self._get_attribute("folder")

    @folder.setter
    @write_only
    @pydantic.validate_call
    def folder(
        self, folder: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)]
    ) -> None:
        """Set the folder for this run."""
        self._staging["folder"] = folder

    @property
    @staging_check
    def metadata(self) -> dict[str, typing.Any]:
        """Get the metadata for this run."""
        return self._get_attribute("metadata")

    @metadata.setter
    @write_only
    @pydantic.validate_call
    def metadata(self, metadata: dict[str, typing.Any]) -> None:
        """Set the metadata for this run."""
        self._staging["metadata"] = metadata

    @property
    @staging_check
    def description(self) -> str:
        """Get the description for this run."""
        return self._get_attribute("description")

    @description.setter
    @write_only
    @pydantic.validate_call
    def description(self, description: str | None) -> None:
        """Set the description for this run."""
        self._staging["description"] = description

    @property
    def system(self) -> dict[str, typing.Any]:
        """Get the system metadata for this run."""
        return self._get_attribute("system")

    @system.setter
    @write_only
    @pydantic.validate_call
    def system(self, system: dict[str, typing.Any]) -> None:
        """Set the system metadata for this run."""
        self._staging["system"] = system

    @property
    @staging_check
    def heartbeat_timeout(self) -> int | None:
        """Get the timeout for the heartbeat of this run."""
        return self._get_attribute("heartbeat_timeout")

    @heartbeat_timeout.setter
    @write_only
    @pydantic.validate_call
    def heartbeat_timeout(self, time_seconds: int | None) -> None:
        self._staging["heartbeat_timeout"] = time_seconds

    @property
    @staging_check
    def notifications(self) -> typing.Literal["none", "all", "error", "lost"]:
        return self._get_attribute("notifications")["state"]

    @notifications.setter
    @write_only
    @pydantic.validate_call
    def notifications(
        self, notifications: typing.Literal["none", "all", "error", "lost"]
    ) -> None:
        self._staging["notifications"] = {"state": notifications}

    @property
    @staging_check
    def alerts(self) -> list[str]:
        if self._offline:
            return self._get_attribute("alerts")

        return [alert["id"] for alert in self.get_alert_details()]

    def get_alert_details(self) -> typing.Generator[dict[str, typing.Any], None, None]:
        """Retrieve the full details of alerts for this run"""
        if self._offline:
            raise RuntimeError(
                "Cannot get alert details from an offline run - use .alerts to access a list of IDs instead"
            )
        for alert in self._get_attribute("alerts"):
            yield alert["alert"]

    @alerts.setter
    @write_only
    @pydantic.validate_call
    def alerts(self, alerts: list[str]) -> None:
        self._staging["alerts"] = list(set(self._staging.get("alerts", []) + alerts))

    @property
    @staging_check
    def created(self) -> datetime.datetime | None:
        """Retrieve created datetime for the run"""
        _created: str | None = self._get_attribute("created")
        return (
            datetime.datetime.strptime(_created, DATETIME_FORMAT) if _created else None
        )

    @created.setter
    @write_only
    @pydantic.validate_call
    def created(self, created: datetime.datetime) -> None:
        self._staging["created"] = created.strftime(DATETIME_FORMAT)

    @property
    @staging_check
    def runtime(self) -> datetime.datetime | None:
        """Retrieve created datetime for the run"""
        _runtime: str | None = self._get_attribute("runtime")
        return time.strptime(_runtime, "%H:%M:%S.%f") if _runtime else None

    @property
    @staging_check
    def started(self) -> datetime.datetime | None:
        """Retrieve started datetime for the run"""
        _started: str | None = self._get_attribute("started")
        return (
            datetime.datetime.strptime(_started, DATETIME_FORMAT) if _started else None
        )

    @started.setter
    @write_only
    @pydantic.validate_call
    def started(self, started: datetime.datetime) -> None:
        self._staging["started"] = started.strftime(DATETIME_FORMAT)

    @property
    @staging_check
    def endtime(self) -> datetime.datetime | None:
        """Retrieve endtime datetime for the run"""
        _endtime: str | None = self._get_attribute("endtime")
        return (
            datetime.datetime.strptime(_endtime, DATETIME_FORMAT) if _endtime else None
        )

    @endtime.setter
    @write_only
    @pydantic.validate_call
    def endtime(self, endtime: datetime.datetime) -> None:
        self._staging["endtime"] = endtime.strftime(DATETIME_FORMAT)

    @property
    def metrics(
        self,
    ) -> typing.Generator[tuple[str, dict[str, int | float | bool]], None, None]:
        yield from self._get_attribute("metrics").items()

    @property
    def events(
        self,
    ) -> typing.Generator[tuple[str, dict[str, int | float | bool]], None, None]:
        yield from self._get_attribute("events").items()

    @write_only
    def send_heartbeat(self) -> dict[str, typing.Any] | None:
        if not self._identifier:
            return None

        if self._offline:
            if not (_dir := self._local_staging_file.parent).exists():
                _dir.mkdir(parents=True)
            _heartbeat_file = self._local_staging_file.with_suffix(".heartbeat")
            _heartbeat_file.touch()
            return None

        _url = self._base_url
        _url /= f"{self._identifier}/heartbeat"
        _response = sv_put(f"{_url}", headers=self._headers, data={})
        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieving heartbeat state",
        )

    @property
    def _abort_url(self) -> URL | None:
        return self.url / "abort" if self.url else None

    @property
    def _artifact_url(self) -> URL | None:
        if not self._identifier or not self.url:
            return None
        _url = self.url
        _url /= "artifacts"
        return _url

    @property
    def abort_trigger(self) -> bool:
        if self._offline or not self._identifier:
            return False

        _response = sv_get(f"{self._abort_url}", headers=self._headers)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieving abort status for run '{self.id}'",
        )
        return _json_response.get("status", False)

    @property
    def artifacts(self) -> list[dict[str, typing.Any]]:
        """Retrieve the artifacts for this run"""
        if self._offline or not self._artifact_url:
            return []

        _response = sv_get(url=self._artifact_url, headers=self._headers)

        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieving artifacts for run '{self.id}'",
            expected_type=list,
        )

    @pydantic.validate_call
    def abort(self, reason: str) -> dict[str, typing.Any]:
        if not self._abort_url:
            raise RuntimeError("Cannot abort run, no endpoint defined")

        _response = sv_put(
            f"{self._abort_url}", headers=self._headers, data={"reason": reason}
        )

        return get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Abort of run '{self.id}'",
            response=_response,
        )

    def on_reconnect(self, id_mapping: dict[str, str]):
        online_alert_ids: list[str] = []
        for id in self._staging.get("alerts", []):
            try:
                online_alert_ids.append(id_mapping[id])
            except KeyError:
                raise KeyError(
                    "Could not find alert ID in offline to online ID mapping."
                )
        # If run is offline, no alerts have been added yet, so add all alerts:
        if self._identifier is not None and self._identifier.startswith("offline"):
            self._staging["alerts"] = online_alert_ids
        # Otherwise, only add alerts which have not yet been added
        else:
            self._staging["alerts"] = [
                id for id in online_alert_ids if id not in list(self.alerts)
            ]
