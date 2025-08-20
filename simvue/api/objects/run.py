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
import json

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from .base import SimvueObject, Sort, staging_check, Visibility, write_only
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

# Need to use this inside of Generator typing to fix bug present in Python 3.10 - see issue #745
T = typing.TypeVar("T", bound="Run")

__all__ = ["Run"]


class RunSort(Sort):
    @pydantic.field_validator("column")
    @classmethod
    def check_column(cls, column: str) -> str:
        if (
            column
            and column != "name"
            and not column.startswith("metrics")
            and not column.startswith("metadata.")
            and column not in ("created", "started", "endtime", "modified")
        ):
            raise ValueError(f"Invalid sort column for runs '{column}'")

        return column


class Run(SimvueObject):
    """Class for directly interacting with/creating runs on the server."""

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        """Initialise a Run.

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

        Examples
        --------

        ```python
        run = Run.new(
            folder="/",
            system=None,
            status="running",
            offline=False
        )
        run.commit()
        ```
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
        """Set/retrieve name associated with this run.

        Returns
        -------
        str
        """
        return self._get_attribute("name")

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> None:
        self._staging["name"] = name

    @property
    @staging_check
    def tags(self) -> list[str]:
        """Set/retrieve the tags associated with this run.

        Returns
        -------
        list[str]
        """
        return self._get_attribute("tags")

    @tags.setter
    @write_only
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        self._staging["tags"] = tags

    @property
    @staging_check
    def status(self) -> Status:
        """Set/retrieve the run status.

        Returns
        -------
        "lost" | "failed" | "completed" | "terminated" | "running" | "created"
        """
        return self._get_attribute("status")

    @status.setter
    @write_only
    @pydantic.validate_call
    def status(self, status: Status) -> None:
        self._staging["status"] = status

    @property
    @staging_check
    def ttl(self) -> int:
        """Set/retrieve the retention period for this run.

        Returns
        -------
        int
        """
        return self._get_attribute("ttl")

    @ttl.setter
    @write_only
    @pydantic.validate_call
    def ttl(self, time_seconds: pydantic.NonNegativeInt | None) -> None:
        self._staging["ttl"] = time_seconds

    @property
    @staging_check
    def folder(self) -> str:
        """Set/retrieve the folder associated with this run.

        Returns
        -------
        str
        """
        return self._get_attribute("folder")

    @folder.setter
    @write_only
    @pydantic.validate_call
    def folder(
        self, folder: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)]
    ) -> None:
        self._staging["folder"] = folder

    @property
    @staging_check
    def metadata(self) -> dict[str, typing.Any]:
        """Set/retrieve the metadata for this run.

        Returns
        -------
        dict[str, Any]
        """
        return self._get_attribute("metadata")

    @metadata.setter
    @write_only
    @pydantic.validate_call
    def metadata(self, metadata: dict[str, typing.Any]) -> None:
        self._staging["metadata"] = metadata

    @property
    def user(self) -> str:
        """Return the user associate with this run."""
        return self._get_attribute("user")

    @property
    @staging_check
    def description(self) -> str:
        """Set/retrieve the description for this run.

        Returns
        -------
        str
        """
        return self._get_attribute("description")

    @description.setter
    @write_only
    @pydantic.validate_call
    def description(self, description: str | None) -> None:
        self._staging["description"] = description

    @property
    def system(self) -> dict[str, typing.Any]:
        """Set/retrieve the system metadata for this run.

        Returns
        -------
        dict[str, Any]
        """
        return self._get_attribute("system")

    @system.setter
    @write_only
    @pydantic.validate_call
    def system(self, system: dict[str, typing.Any]) -> None:
        self._staging["system"] = system

    @property
    @staging_check
    def heartbeat_timeout(self) -> int | None:
        """Set/retrieve the timeout for the heartbeat of this run.

        Returns
        -------
        int | None
        """
        return self._get_attribute("heartbeat_timeout")

    @heartbeat_timeout.setter
    @write_only
    @pydantic.validate_call
    def heartbeat_timeout(self, time_seconds: int | None) -> None:
        self._staging["heartbeat_timeout"] = time_seconds

    @property
    @staging_check
    def notifications(self) -> typing.Literal["none", "all", "error", "lost"]:
        """Set/retrieve the notification state.

        Returns
        -------
        "none" | "all" | "error" | "lost"
        """
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
        """Set/retrieve a list of alert IDs for this run.

        Returns
        -------
        list[str]
        """
        if self._offline:
            return self._get_attribute("alerts")

        return [alert["id"] for alert in self.get_alert_details()]

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.NonNegativeInt | None = None,
        sorting: list[RunSort] | None = None,
        **kwargs,
    ) -> typing.Generator[tuple[str, T | None], None, None]:
        """Get runs from the server.

        Parameters
        ----------
        count : int, optional
            limit the number of objects returned, default no limit.
        offset : int, optional
            start index for results, default is 0.
        sorting : list[dict] | None, optional
            list of sorting definitions in the form {'column': str, 'descending': bool}

        Yields
        ------
        tuple[str, Run]
            id of run
            Run object representing object on server
        """
        _params: dict[str, str] = kwargs

        if sorting:
            _params["sorting"] = json.dumps([i.to_params() for i in sorting])

        return super().get(count=count, offset=offset, **_params)

    @alerts.setter
    @write_only
    @pydantic.validate_call
    def alerts(self, alerts: list[str]) -> None:
        self._staging["alerts"] = list(set(self._staging.get("alerts", []) + alerts))

    def get_alert_details(self) -> typing.Generator[dict[str, typing.Any], None, None]:
        """Retrieve the full details of alerts for this run.

        Yields
        ------
        dict[str, Any]
            alert details for each alert within this run.

        Returns
        -------
        Generator[dict[str, Any], None, None]
        """
        if self._offline:
            raise RuntimeError(
                "Cannot get alert details from an offline run - use .alerts to access a list of IDs instead"
            )
        for alert in self._get_attribute("alerts"):
            yield alert["alert"]

    @property
    @staging_check
    def created(self) -> datetime.datetime | None:
        """Set/retrieve created datetime for the run.

        Returns
        -------
        datetime.datetime
        """
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
        """Retrieve execution time for the run"""
        _runtime: str | None = self._get_attribute("runtime")
        return time.strptime(_runtime, "%H:%M:%S.%f") if _runtime else None

    @property
    @staging_check
    def started(self) -> datetime.datetime | None:
        """Set/retrieve started datetime for the run.

        Returns
        -------
        datetime.datetime
        """
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
        """Set/retrieve endtime datetime for the run.

        Returns
        -------
        datetime.datetime
        """
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
        """Retrieve metrics for this run from the server.

        Yields
        ------
        tuple[str, dict[str, int | float | bool]]
            metric values for this run

        Returns
        -------
        Generator[tuple[str, dict[str, int | float | bool]]
        """
        yield from self._get_attribute("metrics").items()

    @property
    def events(
        self,
    ) -> typing.Generator[tuple[str, dict[str, typing.Any]], None, None]:
        """Returns events information for this run from the server.

        Yields
        ------
        tuple[str, dict[str, Any]]
            event from this run

        Returns
        -------
        Generator[tuple[str, dict[str, Any]]
        """
        yield from self._get_attribute("events").items()

    @write_only
    def send_heartbeat(self) -> dict[str, typing.Any] | None:
        """Send heartbeat signal to the server for this run.

        Returns
        -------
        dict[str, Any]
            server response on heartbeat update.

        """
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
        """Returns the state of the abort run endpoint from the server.

        Returns
        -------
        bool
            the current state of the abort trigger
        """
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
        """Retrieve the artifacts for this run.

        Returns
        -------
        list[dict[str, Any]]
            the artifacts associated with this run
        """
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
        """Trigger an abort for this run by notifying the server.

        Parameters
        ----------
        reason: str
            description of the reason for this abort.

        Returns
        -------
        dict[str, Any]
            server response after updating abort status.

        """
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

    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        """Executed when a run switches from offline to online mode.

        Parameters
        ----------
        id_mapping: dict[str, str]
            A mapping from offline identifier to online identifier.
        """
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
