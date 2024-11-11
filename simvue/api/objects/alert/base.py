import pydantic
import typing
from simvue.api.objects.base import SimvueObject
from simvue.models import NAME_REGEX


class AlertBase(SimvueObject):
    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        self._label = "alert"
        super().__init__(identifier, **kwargs)

    def get_alert(self) -> dict[str, typing.Any]:
        try:
            return self._get()["alert"]
        except KeyError as e:
            raise RuntimeError("Expected key 'alert' in alert retrieval") from e

    @property
    def name(self) -> str:
        try:
            return self._get()["name"]
        except KeyError as e:
            raise RuntimeError("Expected key 'name' in alert retrieval") from e

    @name.setter
    @pydantic.validate_call
    def name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> None:
        self._put(name=name)

    @property
    def description(self) -> str | None:
        try:
            return self._get()["description"]
        except KeyError as e:
            raise RuntimeError("Expected key 'description' in alert retrieval") from e

    @description.setter
    @pydantic.validate_call
    def description(self, description: str | None) -> None:
        self._put(description=description)

    @property
    def tags(self) -> list[str]:
        try:
            return self._get()["tags"] or []
        except KeyError as e:
            raise RuntimeError("Expected key 'tags' in alert retrieval") from e

    @tags.setter
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        self._put(tags=tags)

    @property
    def notification(self) -> typing.Literal["none", "email"]:
        try:
            return self._get()["notification"]
        except KeyError as e:
            raise RuntimeError("Expected key 'notification' in alert retrieval") from e

    @notification.setter
    @pydantic.validate_call
    def notification(self, notification: typing.Literal["none", "email"]) -> None:
        self._put(notification=notification)

    @property
    def source(self) -> typing.Literal["events", "metrics", "user"]:
        try:
            return self._get()["source"]
        except KeyError as e:
            raise RuntimeError("Expected key 'source' in alert retrieval") from e

    @property
    def enabled(self) -> bool:
        try:
            return self._get()["enabled"]
        except KeyError as e:
            raise RuntimeError("Expected key 'enabled' in alert retrieval") from e

    @enabled.setter
    @pydantic.validate_call
    def enabled(self, enabled: str) -> None:
        self._put(enabled=enabled)

    @property
    def abort(self) -> bool:
        try:
            return self._get()["abort"]
        except KeyError as e:
            raise RuntimeError("Expected key 'abort' in alert retrieval") from e

    @abort.setter
    @pydantic.validate_call
    def abort(self, abort: str) -> None:
        self._put(abort=abort)
