import typing
import pydantic
from .base import AlertBase, staging_check
from simvue.models import NAME_REGEX


class EventsAlert(AlertBase):
    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        self.alert = EventAlertDefinition(self)
        super().__init__(identifier, **kwargs)

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
        tags: list[str] | None = None,
    ) -> typing.Self:
        _alert = EventsAlert()
        _alert_definition = {"pattern": pattern, "frequency": frequency}
        _alert._post(
            name=name,
            notification=notification,
            source="events",
            alert=_alert_definition,
            enabled=enabled,
            tags=tags or [],
        )
        return _alert


class EventAlertDefinition:
    def __init__(self, alert: EventsAlert) -> None:
        self._alert = alert

    @property
    def pattern(self) -> str:
        try:
            return self._alert.get_alert()["pattern"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'pattern' in alert definition retrieval"
            ) from e

    @property
    @staging_check
    def frequency(self) -> int:
        try:
            return self._alert.get_alert()["frequency"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @frequency.setter
    @pydantic.validate_call
    def frequency(self, frequency: int) -> None:
        _alert = self._alert.get_alert() | {"frequency": frequency}
        self._alert._staging["alert"] = _alert
