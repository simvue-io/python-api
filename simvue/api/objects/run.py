import typing
import pydantic
import datetime
from .base import SimvueObject, staging_check, Visibility
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
    ):
        """Create a new Folder on the Simvue server with the given path"""
        _run = Run(folder=folder, system=None, status="created")
        _run.offline_mode(offline)
        return _run

    @property
    @staging_check
    def name(self) -> str:
        return self._get_attribute("name")

    @name.setter
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
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        self._staging["tags"] = tags

    @property
    @staging_check
    def status(self) -> Status:
        return self._get_attribute("status")

    @status.setter
    @pydantic.validate_call
    def status(self, status: Status) -> None:
        self._staging["status"] = status

    @property
    @staging_check
    def ttl(self) -> int:
        """Return the retention period for this run"""
        return self._get_attribute("ttl")

    @ttl.setter
    @pydantic.validate_call
    def ttl(self, time_seconds: int) -> None:
        """Update the retention period for this run"""
        self._staging["ttl"] = time_seconds

    @property
    @staging_check
    def folder(self) -> str:
        return self._get_attribute("folder")

    @folder.setter
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
    @pydantic.validate_call
    def metadata(self, metadata: dict[str, typing.Any]) -> None:
        self._staging["metadata"] = metadata

    @property
    @staging_check
    def description(self) -> str:
        return self._get_attribute("description")

    @description.setter
    @pydantic.validate_call
    def description(self, description: str) -> None:
        self._staging["description"] = description

    @property
    def system(self) -> dict[str, typing.Any]:
        return self._get_attribute("system")

    @property
    @staging_check
    def heartbeat_timeout(self) -> int:
        return self._get_attribute("heartbeat_timeout")

    @heartbeat_timeout.setter
    @pydantic.validate_call
    def heartbeat_timeout(self, time_seconds: int) -> None:
        self._staging["heartbeat_timeout"] = time_seconds

    @property
    @staging_check
    def notifications(self) -> typing.Literal["none", "email"]:
        return self._get_attribute("notifications")

    @notifications.setter
    @pydantic.validate_call
    def notifications(self, notifications: typing.Literal["none", "email"]) -> None:
        self._staging["notifications"] = notifications

    @property
    @staging_check
    def alerts(self) -> list[str]:
        return self._get_attribute("alerts")

    @alerts.setter
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
    @pydantic.validate_call
    def endtime(self, endtime: datetime.datetime) -> None:
        self._staging["endtime"] = endtime.strftime(DATETIME_FORMAT)
