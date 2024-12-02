import http
import typing
import pydantic
import datetime

from .base import SimvueObject, staging_check, Visibility, write_only
from simvue.api.request import get as sv_get, put as sv_put, get_json_from_response
from simvue.api.url import URL
from simvue.models import FOLDER_REGEX, NAME_REGEX, DATETIME_FORMAT

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

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        folder: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
        offline: bool = False,
    ) -> typing.Self:
        """Create a new Folder on the Simvue server with the given path"""
        _run = Run(folder=folder, system=None, status="created", _read_only=False)
        _run.offline_mode(offline)
        return _run

    @property
    @staging_check
    def name(self) -> str:
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
        for alert in self._get_attribute("alerts"):
            yield alert["alert"]["id"]

    @alerts.setter
    @write_only
    @pydantic.validate_call
    def alerts(self, alerts: list[str]) -> None:
        self._staging["alerts"] = alerts

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
    def endtime(self) -> datetime.datetime:
        return datetime.datetime.strptime(
            self._get_attribute("endtime"), DATETIME_FORMAT
        )

    @endtime.setter
    @write_only
    @pydantic.validate_call
    def endtime(self, endtime: datetime.datetime) -> None:
        self._staging["endtime"] = endtime.strftime(DATETIME_FORMAT)

    @write_only
    def send_heartbeat(self) -> dict[str, typing.Any] | None:
        if self._offline or not self._identifier:
            return None

        _url = self._base_url
        _url /= f"heartbeat/{self._identifier}"
        _response = sv_put(f"{_url}", headers=self._headers, data={})
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieving abort status",
        )
        if not isinstance(_json_response, dict):
            raise RuntimeError(
                f"Expected dictionary from JSON response during {self._label} abort status check "
                f"but got '{type(_json_response)}'"
            )
        return _json_response

    @property
    def _abort_url(self) -> URL | None:
        if not self._identifier:
            return None
        _url = self._base_url
        _url /= f"abort/{self._identifier}"
        return _url

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
        if not isinstance(_json_response, dict):
            raise RuntimeError(
                f"Expected dictionary from JSON response during {self._label} abort status check "
                f"but got '{type(_json_response)}'"
            )
        return _json_response.get("status", False)

    @property
    def artifacts(self) -> list[dict[str, typing.Any]]:
        """Retrieve the artifacts for this run"""
        if self._offline or not self._artifact_url:
            return []

        _response = sv_get(url=self._artifact_url, headers=self._headers)

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieving artifacts for run '{self.id}'",
        )

        if not isinstance(_json_response, list):
            raise RuntimeError(
                f"Expected list from JSON response during {self._label} "
                f"'{self.id}' artifact retrieval "
                f"but got '{type(_json_response)}'"
            )

        return _json_response

    @pydantic.validate_call
    def abort(self, reason: str) -> dict[str, typing.Any]:
        if not self._abort_url:
            return {}

        _url = self._abort_url / self._identifier

        _response = sv_put(f"{_url}", headers=self._headers, data={"reason": reason})

        _json_response = get_json_from_response(
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Abort of run '{self.id}'",
            response=_response,
        )

        if not isinstance(_json_response, dict):
            raise RuntimeError(
                "Expected dict from JSON response during abort of "
                f"run but got '{type(_json_response)}'"
            )

        return _json_response
