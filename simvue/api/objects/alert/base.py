"""
Alert Object Base
=================

Contains general definitions for Simvue Alert objects.

"""

import http
import pydantic
import datetime
import typing
from simvue.api.objects.base import SimvueObject, staging_check, write_only
from simvue.api.request import get as sv_get, get_json_from_response
from simvue.api.url import URL
from simvue.models import NAME_REGEX, DATETIME_FORMAT


class AlertBase(SimvueObject):
    """Class for interfacing with Simvue alerts

    Contains properties common to all alert types.
    """

    @classmethod
    def new(cls, **kwargs):
        """Create a new alert"""
        pass

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        """Retrieve an alert from the Simvue server by identifier"""
        self._label = "alert"
        super().__init__(identifier=identifier, **kwargs)

    def compare(self, other: "AlertBase") -> bool:
        """Compare this alert to another"""
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
    @write_only
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
    @write_only
    @pydantic.validate_call
    def description(self, description: str | None) -> None:
        """Set alert description"""
        self._staging["description"] = description

    @property
    def run_tags(self) -> list[str]:
        """Retrieve automatically assigned tags from runs"""
        return self._get_attribute("run_tags")

    @property
    @staging_check
    def auto(self) -> bool:
        """Retrieve if alert has run tag auto-assign"""
        return self._get_attribute("auto")

    @auto.setter
    @write_only
    @pydantic.validate_call
    def auto(self, auto: bool) -> None:
        """Set alert to use run tag auto-assign"""
        self._staging["auto"] = auto

    @property
    @staging_check
    def notification(self) -> typing.Literal["none", "email"]:
        """Retrieve alert notification setting"""
        return self._get_attribute("notification")

    @notification.setter
    @write_only
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
    @write_only
    @pydantic.validate_call
    def enabled(self, enabled: str) -> None:
        """Enable/disable alert"""
        self._staging["enabled"] = enabled

    @property
    @staging_check
    def abort(self) -> bool:
        """Retrieve if alert can abort simulations"""
        return self._get_attribute("abort")

    @property
    @staging_check
    def delay(self) -> int:
        """Retrieve delay value for this alert"""
        return self._get_attribute("delay")

    @property
    def created(self) -> datetime.datetime | None:
        """Retrieve created datetime for the alert"""
        _created: str | None = self._get_attribute("created")
        return (
            datetime.datetime.strptime(_created, DATETIME_FORMAT) if _created else None
        )

    @abort.setter
    @write_only
    @pydantic.validate_call
    def abort(self, abort: bool) -> None:
        """Configure alert to trigger aborts"""
        self._staging["abort"] = abort

    @pydantic.validate_call
    def set_status(self, run_id: str, status: typing.Literal["ok", "critical"]) -> None:
        """Set the status of this alert for a given run"""
        raise AttributeError(
            f"Cannot update state for alert of type '{self.__class__.__name__}'"
        )

    def get_status(self, run_id: str) -> typing.Literal["ok", "critical"]:
        """Retrieve the status of this alert for a given run"""
        _url: URL = self.url / f"status/{run_id}"
        _response = sv_get(url=f"{_url}", headers=self._headers)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieving status for alert '{self.id}' in run '{run_id}'",
        )

        return _json_response.get("status")
