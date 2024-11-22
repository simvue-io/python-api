"""
Alert Object Base
=================

Contains general definitions for Simvue Alert objects.

"""

import pydantic
import typing
from simvue.api.objects.base import SimvueObject, staging_check
from simvue.models import NAME_REGEX


class AlertBase(SimvueObject):
    """Class for interfacing with Simvue alerts

    Contains properties common to all alert types.
    """

    @classmethod
    def new(cls, **kwargs):
        pass

    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        """Retrieve an alert from the Simvue server by identifier"""
        self._label = "alert"
        super().__init__(identifier, **kwargs)

    def compare(self, other: "AlertBase") -> bool:
        return type(self) is type(other) and self.name == other.name

    @staging_check
    def get_alert(self) -> dict[str, typing.Any]:
        """Retrieve alert definition"""
        try:
            return self._get_attribute("alert")
        except AttributeError:
            return {}

    @property
    def name(self) -> str:
        """Retrieve alert name"""
        return self._get_attribute("name")

    @name.setter
    @pydantic.validate_call
    def name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> None:
        """Set alert name"""
        self._staging["name"] = name

    @property
    @staging_check
    def description(self) -> str | None:
        """Retrieve alert description"""
        return self._get_attribute("description")

    @description.setter
    @pydantic.validate_call
    def description(self, description: str | None) -> None:
        """Set alert description"""
        self._staging["description"] = description

    @property
    @staging_check
    def tags(self) -> list[str]:
        """Retrieve alert tags"""
        return self._get_attribute("tags")

    @tags.setter
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        """Set alert tags"""
        self._staging["tags"] = tags

    @property
    @staging_check
    def notification(self) -> typing.Literal["none", "email"]:
        """Retrieve alert notification setting"""
        return self._get_attribute("notification")

    @notification.setter
    @pydantic.validate_call
    def notification(self, notification: typing.Literal["none", "email"]) -> None:
        """Configure alert notification setting"""
        self._staging["notification"] = notification

    @property
    def source(self) -> typing.Literal["events", "metrics", "user"]:
        """Retrieve alert source"""
        return self._get_attribute("source")

    @property
    @staging_check
    def enabled(self) -> bool:
        """Retrieve if alert is enabled"""
        return self._get_attribute("enabled")

    @enabled.setter
    @pydantic.validate_call
    def enabled(self, enabled: str) -> None:
        """Enable/disable alert"""
        self._staging["enabled"] = enabled

    @property
    @staging_check
    def abort(self) -> bool:
        """Retrieve if alert can abort simulations"""
        return self._get_attribute("abort")

    @abort.setter
    @pydantic.validate_call
    def abort(self, abort: str) -> None:
        """Configure alert to trigger aborts"""
        self._staging["abort"] = abort
