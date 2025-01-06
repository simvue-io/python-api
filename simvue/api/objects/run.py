import http
import typing
import msgpack
import pydantic
import datetime

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from .base import SimvueObject, staging_check, Visibility, write_only
from simvue.api.request import (
    get as sv_get,
    put as sv_put,
    get_json_from_response,
    post as sv_post,
)
from simvue.api.url import URL
from simvue.models import FOLDER_REGEX, NAME_REGEX, DATETIME_FORMAT, EventSet, MetricSet

Status = typing.Literal[
    "lost", "failed", "completed", "terminated", "running", "created"
]

__all__ = ["Run"]


class Run(SimvueObject):
    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
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

        self._staged_metrics: list[dict[str, str | dict | int]] = (
            self._get_local_staged("metrics").get(self._identifier)  # type: ignore
            if self._identifier
            else []
        )

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        folder: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
        offline: bool = False,
    ) -> Self:
        """Create a new Folder on the Simvue server with the given path"""
        _run = Run(folder=folder, system=None, status="created", _read_only=False)
        _run.offline_mode(offline)
        return _run

    @property
    @staging_check
    def name(self) -> str:
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
        self._staging["name"] = name

    @property
    @staging_check
    def tags(self) -> list[str]:
        return self._get_attribute("tags")

    @tags.setter
    @write_only
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        self._staging["tags"] = tags

    @property
    @staging_check
    def status(self) -> Status:
        return self._get_attribute("status")

    @status.setter
    @write_only
    @pydantic.validate_call
    def status(self, status: Status) -> None:
        self._staging["status"] = status

    @property
    @staging_check
    def ttl(self) -> int:
        """Return the retention period for this run"""
        return self._get_attribute("ttl")

    @ttl.setter
    @write_only
    @pydantic.validate_call
    def ttl(self, time_seconds: int | None) -> None:
        """Update the retention period for this run"""
        self._staging["ttl"] = time_seconds

    @property
    @staging_check
    def folder(self) -> str:
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
        return self._get_attribute("metadata")

    @metadata.setter
    @write_only
    @pydantic.validate_call
    def metadata(self, metadata: dict[str, typing.Any]) -> None:
        self._staging["metadata"] = metadata

    @property
    @staging_check
    def description(self) -> str:
        return self._get_attribute("description")

    @description.setter
    @write_only
    @pydantic.validate_call
    def description(self, description: str) -> None:
        self._staging["description"] = description

    @property
    def system(self) -> dict[str, typing.Any]:
        return self._get_attribute("system")

    @system.setter
    @write_only
    @pydantic.validate_call
    def system(self, system: dict[str, typing.Any]) -> None:
        self._staging["system"] = system

    @property
    @staging_check
    def heartbeat_timeout(self) -> int:
        return self._get_attribute("heartbeat_timeout")

    @heartbeat_timeout.setter
    @write_only
    @pydantic.validate_call
    def heartbeat_timeout(self, time_seconds: int) -> None:
        self._staging["heartbeat_timeout"] = time_seconds

    @property
    @staging_check
    def notifications(self) -> typing.Literal["none", "email"]:
        return self._get_attribute("notifications")

    @notifications.setter
    @write_only
    @pydantic.validate_call
    def notifications(self, notifications: typing.Literal["none", "email"]) -> None:
        self._staging["notifications"] = notifications

    @property
    @staging_check
    def alerts(self) -> typing.Generator[str, None, None]:
        for alert in self.get_alert_details():
            yield alert["id"]

    def get_alert_details(self) -> typing.Generator[dict[str, typing.Any], None, None]:
        """Retrieve the full details of alerts for this run"""
        for alert in self._get_attribute("alerts"):
            yield alert["alert"]

    @alerts.setter
    @write_only
    @pydantic.validate_call
    def alerts(self, alerts: list[str]) -> None:
        self._staging["alerts"] = [
            alert for alert in alerts if alert not in self._staging.get("alerts", [])
        ]

    @property
    @staging_check
    def created(self) -> datetime.datetime:
        return datetime.datetime.strptime(
            self._get_attribute("created"), DATETIME_FORMAT
        )

    @created.setter
    @write_only
    @pydantic.validate_call
    def created(self, created: datetime.datetime) -> None:
        self._staging["created"] = created.strftime(DATETIME_FORMAT)

    @property
    @staging_check
    def started(self) -> datetime.datetime:
        return datetime.datetime.strptime(
            self._get_attribute("started"), DATETIME_FORMAT
        )

    @started.setter
    @write_only
    @pydantic.validate_call
    def started(self, started: datetime.datetime) -> None:
        self._staging["started"] = started.strftime(DATETIME_FORMAT)

    @property
    @staging_check
    def endtime(self) -> datetime.datetime | None:
        _endtime: str | None = self._get_attribute("endtime", None)
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
        if self._staged_metrics:
            self._logger.warning(f"Uncommitted metrics found for run '{self.id}'")
        yield from self._get_attribute("metrics").items()

    @property
    def events(
        self,
    ) -> typing.Generator[tuple[str, dict[str, int | float | bool]], None, None]:
        if self._staged_metrics:
            self._logger.warning(f"Uncommitted metrics found for run '{self.id}'")
        yield from self._get_attribute("events").items()

    @pydantic.validate_call
    def log_entries(
        self,
        entry_type: typing.Literal["metrics", "events"],
        entries: list[MetricSet | EventSet],
    ) -> None:
        """Add entries to server or local staging"""
        if not self._identifier:
            raise RuntimeError("Cannot stage metrics, no identifier found")

        _validated_entries: list[dict] = [entry.model_dump() for entry in entries]

        if self._offline or self._identifier.startswith("offline_"):
            self._stage_to_other(entry_type, self._identifier, _validated_entries)
            return

        _url = URL(self._user_config.server.url) / entry_type
        _data = {entry_type: _validated_entries, "run": self._identifier}
        _data_bin = msgpack.packb(_data, use_bin_type=True)

        _msgpack_header = self._headers | {"Content-Type": "application/msgpack"}

        _response = sv_post(
            f"{_url}", headers=_msgpack_header, data=_data_bin, is_json=False
        )

        get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Logging of {entry_type} '{entries}' for run '{self.id}'",
            allow_parse_failure=True,
        )

    @write_only
    def send_heartbeat(self) -> dict[str, typing.Any] | None:
        if self._offline or not self._identifier:
            return None

        _url = self._base_url
        _url /= f"{self._identifier}/heartbeat"
        _response = sv_put(f"{_url}", headers=self._headers, data={})
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieving heartbeat state",
        )
        return _json_response

    @property
    def _abort_url(self) -> URL | None:
        if not self._identifier:
            return None
        return self.url / "abort"

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
            return {}

        _response = sv_put(
            f"{self._abort_url}", headers=self._headers, data={"reason": reason}
        )

        return get_json_from_response(
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Abort of run '{self.id}'",
            response=_response,
        )
