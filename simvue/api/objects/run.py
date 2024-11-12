import typing
import pydantic
import datetime
from .base import SimvueObject, staging_check, Visibility
from simvue.models import FOLDER_REGEX, NAME_REGEX, DATETIME_FORMAT

Status = typing.Literal[
    "lost", "failed", "completed", "terminated", "running", "created"
]


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
    ):
        """Create a new Folder on the Simvue server with the given path"""
        _run = Run()
        _run._post(folder=folder, system=None, status="created")
        return _run

    @property
    @staging_check
    def name(self) -> str:
        try:
            return self._get()["name"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'name' for run '{self._identifier}'"
            ) from e

    @name.setter
    @pydantic.validate_call
    def name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> None:
        self._staging["name"] = name

    @property
    @staging_check
    def tags(self) -> list[str]:
        try:
            return self._get()["tags"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'tags' for run '{self._identifier}'"
            ) from e

    @tags.setter
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        self._staging["tags"] = tags

    @property
    @staging_check
    def status(self) -> Status:
        if not (_status := self._get().get("status")):
            raise RuntimeError(
                f"Expected value for 'status' for run '{self._identifier}'"
            )
        return _status

    @status.setter
    @pydantic.validate_call
    def status(self, status: Status) -> None:
        self._staging["status"] = status

    @property
    @staging_check
    def ttl(self) -> int:
        """Return the retention period for this run"""
        try:
            return self._get()["ttl"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'ttl' for run '{self._identifier}'"
            ) from e

    @ttl.setter
    @pydantic.validate_call
    def ttl(self, time_seconds: int) -> None:
        """Update the retention period for this run"""
        self._staging["ttl"] = time_seconds

    @property
    @staging_check
    def folder(self) -> str:
        if not (_folder := self._get().get("folder")):
            raise RuntimeError(
                f"Expected value for 'folder' for run '{self._identifier}'"
            )
        return _folder

    @folder.setter
    @pydantic.validate_call
    def folder(
        self, folder: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)]
    ) -> None:
        self._staging["folder"] = folder

    @property
    @staging_check
    def metadata(self) -> dict[str, typing.Any]:
        if not (_metadata := self._get().get("metadata")):
            raise RuntimeError(
                f"Expected value for 'metadata' for run '{self._identifier}'"
            )
        return _metadata

    @metadata.setter
    @pydantic.validate_call
    def metadata(self, metadata: dict[str, typing.Any]) -> None:
        self._staging["metadata"] = metadata

    @property
    @staging_check
    def description(self) -> str:
        if not (_description := self._get().get("description")):
            raise RuntimeError(
                f"Expected value for 'description' for run '{self._identifier}'"
            )
        return _description

    @description.setter
    @pydantic.validate_call
    def description(self, description: str) -> None:
        self._staging["description"] = description

    @property
    def system(self) -> dict[str, typing.Any]:
        if not (_system := self._get().get("system")):
            raise RuntimeError(
                f"Expected value for 'descriptio' for run '{self._identifier}'"
            )
        return _system

    @property
    @staging_check
    def heartbeat_timeout(self) -> int:
        if not (_heartbeat_timeout := self._get().get("heartbeat_timeout")):
            raise RuntimeError(
                f"Expected value for 'heartbeat_timeout' for run '{self._identifier}'"
            )
        return _heartbeat_timeout

    @heartbeat_timeout.setter
    @pydantic.validate_call
    def heartbeat_timeout(self, time_seconds: int) -> None:
        self._staging["heartbeat_timeout"] = time_seconds

    @property
    @staging_check
    def notifications(self) -> typing.Literal["none", "email"]:
        try:
            return self._get()["notifications"]
        except KeyError as e:
            raise RuntimeError("Expected key 'notifications' in alert retrieval") from e

    @notifications.setter
    @pydantic.validate_call
    def notifications(self, notifications: typing.Literal["none", "email"]) -> None:
        self._staging["notifications"] = notifications

    @property
    @staging_check
    def alerts(self) -> list[str]:
        try:
            return self._get()["alerts"]
        except KeyError as e:
            raise RuntimeError("Expected key 'alerts' in alert retrieval") from e

    @alerts.setter
    @pydantic.validate_call
    def alerts(self, alerts: list[str]) -> None:
        self._staging["alerts"] = alerts

    @property
    @staging_check
    def created(self) -> datetime.datetime:
        try:
            return datetime.datetime.strptime(self._get()["created"], DATETIME_FORMAT)
        except KeyError as e:
            raise RuntimeError("Expected key 'created' in alert retrieval") from e

    @created.setter
    @pydantic.validate_call
    def created(self, created: datetime.datetime) -> None:
        self._staging["created"] = created.strftime(DATETIME_FORMAT)

    @property
    @staging_check
    def started(self) -> datetime.datetime:
        try:
            return datetime.datetime.strptime(self._get()["started"], DATETIME_FORMAT)
        except KeyError as e:
            raise RuntimeError("Expected key 'started' in alert retrieval") from e

    @started.setter
    @pydantic.validate_call
    def started(self, started: datetime.datetime) -> None:
        self._staging["started"] = started.strftime(DATETIME_FORMAT)

    @property
    @staging_check
    def endtime(self) -> datetime.datetime:
        try:
            return datetime.datetime.strptime(self._get()["endtime"], DATETIME_FORMAT)
        except KeyError as e:
            raise RuntimeError("Expected key 'endtime' in alert retrieval") from e

    @endtime.setter
    @pydantic.validate_call
    def endtime(self, endtime: datetime.datetime) -> None:
        self._staging["endtime"] = endtime.strftime(DATETIME_FORMAT)
