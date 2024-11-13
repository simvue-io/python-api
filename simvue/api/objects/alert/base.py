import pydantic
import typing
from simvue.api.objects.base import SimvueObject, staging_check
from simvue.models import NAME_REGEX


class AlertBase(SimvueObject):
    @classmethod
    def new(cls, offline: bool = False, **kwargs):
        _alert = AlertBase(**kwargs)
        _alert.offline_mode(offline)
        return _alert

    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        self._label = "alert"
        super().__init__(identifier, **kwargs)

    def get_alert(self) -> dict[str, typing.Any]:
        try:
            return self._get_attribute("alert")
        except AttributeError:
            return {}

    @property
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
    def description(self) -> str | None:
        return self._get_attribute("description")

    @description.setter
    @pydantic.validate_call
    def description(self, description: str | None) -> None:
        self._staging["description"] = description

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
    def notification(self) -> typing.Literal["none", "email"]:
        return self._get_attribute("notification")

    @notification.setter
    @pydantic.validate_call
    def notification(self, notification: typing.Literal["none", "email"]) -> None:
        self._staging["notification"] = notification

    @property
    def source(self) -> typing.Literal["events", "metrics", "user"]:
        return self._get_attribute("source")

    @property
    @staging_check
    def enabled(self) -> bool:
        return self._get_attribute("enabled")

    @enabled.setter
    @pydantic.validate_call
    def enabled(self, enabled: str) -> None:
        self._staging["enabled"] = enabled

    @property
    @staging_check
    def abort(self) -> bool:
        return self._get_attribute("abort")

    @abort.setter
    @pydantic.validate_call
    def abort(self, abort: str) -> None:
        self._staging["abort"] = abort
