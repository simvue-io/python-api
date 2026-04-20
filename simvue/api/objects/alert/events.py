"""Simvue Event Alerts.

Interface to event-based Simvue alerts.

"""

import typing
from collections.abc import Generator

import pydantic

try:
    from typing import Self, override
except ImportError:
    from typing_extensions import Self, override  # noqa: UP035

from simvue.api.objects.base import staging_check, write_only
from simvue.models import NAME_REGEX

from .base import AlertBase, staging_check


class EventsAlert(AlertBase):
    """
    Simvue Events Alert
    ===================

    This class is used to connect to/create event-based alert objects on the Simvue server,
    any modification of EventsAlert instance attributes is mirrored on the remote object.

    """

    def __init__(self, identifier: str | None = None, **kwargs: object) -> None:
        """Initialise an Events Alert

        If an identifier is provided a connection will be made to the
        object matching the identifier on the target server.
        Else a new EventsAlert instance will be created using arguments provided in kwargs.

        Parameters
        ----------
        identifier : str, optional
            the remote server unique id for the target folder
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        self.alert = EventAlertDefinition(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @override
    def get(
        cls,
        *,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.NonNegativeInt | None = None,
        **kwargs: object,
    ) -> Generator[tuple[str, Self]]:
        """Retrieve only alerts of the event alert type."""
        raise NotImplementedError("Retrieval of only event alerts is not yet supported")

    @classmethod
    @pydantic.validate_call
    @override
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        description: str | None,
        notification: typing.Literal["none", "email"],
        pattern: str,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        offline: bool = False,
        **_: object,
    ) -> Self:
        """Create a new event-based alert.

        Note parameters are keyword arguments only.

        Parameters
        ----------
        name : str
            name of the alert
        description : str | None
            description for this alert
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

        Returns
        -------
        EventAlert
           a new event alert with changes staged

        """
        _alert_definition = {"pattern": pattern, "frequency": frequency}
        _alert = cls(
            name=name,
            description=description,
            notification=notification,
            source="events",
            alert=_alert_definition,
            enabled=enabled,
            _read_only=False,
            _offline=offline,
        )
        _alert._staging |= _alert_definition
        _alert._params = {"deduplicate": True}  # pyright: ignore[reportAttributeAccessIssue]
        return _alert

    @override
    def _compare_objects(self, other: "AlertBase") -> bool:
        """Compare Events Alerts."""
        if not isinstance(other, EventsAlert):
            return False
        return super()._compare_objects(other) and self.alert == other.alert


class EventAlertDefinition:
    """Event alert definition sub-class."""

    def __init__(self, alert: EventsAlert) -> None:
        """Initialise an alert definition with its parent alert."""
        self._sv_obj: EventsAlert = alert

    @override
    def __eq__(self, other: "EventAlertDefinition") -> bool:
        """Compare this definition with that of another EventAlert"""
        return all(
            [
                self.frequency == other.frequency,
                self.pattern == other.pattern,
            ]
        )

    @property
    def pattern(self) -> str | None:
        """Retrieve the event log pattern monitored by this alert."""
        _alert = self._sv_obj.get_alert()
        if not _alert:
            _out_msg: str = f"{self.__class__.__name__} object has no alert definition."
            raise RuntimeError(_out_msg)
        try:
            return _alert["pattern"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'pattern' in alert definition retrieval"
            ) from e

    @property
    @staging_check
    def frequency(self) -> int:
        """Retrieve the update frequency for this alert."""
        _alert = self._sv_obj.get_alert()
        if not _alert:
            _out_msg: str = f"{self.__class__.__name__} object has no alert definition."
            raise RuntimeError(_out_msg)
        try:
            return _alert["frequency"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @frequency.setter
    @write_only
    @pydantic.validate_call
    def frequency(self, frequency: int) -> None:
        """Set the update frequency for this alert."""
        _alert: dict[str, object] = self._sv_obj.get_alert()
        if not _alert:
            _out_msg: str = f"{self.__class__.__name__} object has no alert definition."
            raise RuntimeError(_out_msg)
        _alert |= {"frequency": frequency}
        self._sv_obj._staging["alert"] = _alert  # noqa: SLF001
