"""
Simvue Event Alerts
===================

Interface to event-based Simvue alerts.

"""

import typing
import pydantic

from simvue.api.objects.base import write_only
from .base import AlertBase, staging_check
from simvue.models import NAME_REGEX


class EventsAlert(AlertBase):
    """Connect to an event-based alert either locally or on a server"""

    def __init__(
        self, identifier: str | None = None, read_only: bool = False, **kwargs
    ) -> None:
        """Initialise a connection to an event alert by identifier"""
        self.alert = EventAlertDefinition(self)
        super().__init__(identifier, read_only, **kwargs)

    @classmethod
    def get_all(
        cls, count: int | None = None, offset: int | None = None
    ) -> dict[str, typing.Any]:
        raise NotImplementedError("Retrieve of only event alerts is not yet supported")

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        notification: typing.Literal["none", "email"],
        pattern: str,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new event-based alert

        Note parameters are keyword arguments only.

        Parameters
        ----------
        name : str
            name of the alert
        notification : "none" | "email"
            configure notifications sent by this alert
        pattern : str
            pattern to monitor in event logs
        frequency : int
            how often to check for updates
        enabled : bool, optional
            enable this alert upon creation, default is True
        offline : bool, optional
            create alert locally, default is False

        """

        _alert_definition = {"pattern": pattern, "frequency": frequency}
        _alert = EventsAlert(
            name=name,
            notification=notification,
            source="events",
            alert=_alert_definition,
            enabled=enabled,
        )
        _alert.offline_mode(offline)
        return _alert


class EventAlertDefinition:
    """Event alert definition sub-class"""

    def __init__(self, alert: EventsAlert) -> None:
        """Initialise an alert definition with its parent alert"""
        self._sv_obj = alert

    @property
    def pattern(self) -> str:
        """Retrieve the event log pattern monitored by this alert"""
        try:
            return self._sv_obj.get_alert()["pattern"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'pattern' in alert definition retrieval"
            ) from e

    @property
    @staging_check
    def frequency(self) -> int:
        """Retrieve the update frequency for this alert"""
        try:
            return self._sv_obj.get_alert()["frequency"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @frequency.setter
    @write_only
    @pydantic.validate_call
    def frequency(self, frequency: int) -> None:
        """Set the update frequency for this alert"""
        _alert = self._sv_obj.get_alert() | {"frequency": frequency}
        self._sv_obj._staging["alert"] = _alert
