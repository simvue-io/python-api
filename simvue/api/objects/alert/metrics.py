import pydantic
import typing
from .base import AlertBase
from simvue.models import NAME_REGEX

Aggregate = typing.Literal["average", "sum", "at least one", "all"]
Rule = typing.Literal["is above", "is below", "is inside range", "is outside range"]


class MetricsAlert(AlertBase):
    @property
    def aggregation(self) -> Aggregate:
        if not (_aggregation := self.alert.get_alert().get("aggregation")):
            raise RuntimeError(
                "Expected key 'aggregation' in alert definition retrieval"
            )
        return _aggregation

    @property
    def rule(self) -> Rule:
        if not (_rule := self.alert.get_alert().get("rule")):
            raise RuntimeError("Expected key 'rule' in alert definition retrieval")
        return _rule

    @property
    def window(self) -> int:
        if not (_window := self.alert.get_alert().get("window")):
            raise RuntimeError("Expected key 'window' in alert definition retrieval")
        return _window

    @property
    def frequency(self) -> int:
        try:
            return self.alert.get_alert()["frequency"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @frequency.setter
    @pydantic.validate_call
    def frequency(self, frequency: int) -> None:
        self.alert._put(frequency=frequency)


class MetricsThresholdAlert(MetricsAlert):
    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        self.alert = MetricThresholdAlertDefinition(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        notification: typing.Literal["none", "email"],
        aggregation: Aggregate,
        rule: Rule,
        window: pydantic.PositiveInt,
        threshold: float,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        tags: list[str] | None = None,
    ) -> typing.Self:
        _alert = MetricsThresholdAlert()
        _alert_definition = {
            "rule": rule,
            "frequency": frequency,
            "window": window,
            "aggregation": aggregation,
            "threshold": threshold,
        }
        _alert._post(
            name=name,
            notification=notification,
            source="events",
            alert=_alert_definition,
            enabled=enabled,
            tags=tags or [],
        )
        return _alert


class MetricsRangeAlert(AlertBase):
    def __init__(self, identifier: str, **kwargs) -> None:
        self.alert = MetricRangeAlertDefinition(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        notification: typing.Literal["none", "email"],
        aggregation: Aggregate,
        rule: Rule,
        window: pydantic.PositiveInt,
        range_high: float,
        range_low: float,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        tags: list[str] | None = None,
    ) -> typing.Self:
        if range_low >= range_high:
            raise ValueError(f"Invalid arguments for range [{range_low}, {range_high}]")

        _alert = MetricsThresholdAlert()
        _alert_definition = {
            "rule": rule,
            "frequency": frequency,
            "window": window,
            "aggregation": aggregation,
            "range_low": range_low,
            "range_high": range_high,
        }
        _alert._post(
            name=name,
            notification=notification,
            source="events",
            alert=_alert_definition,
            enabled=enabled,
            tags=tags or [],
        )
        return _alert


class MetricThresholdAlertDefinition:
    def __init__(self, alert: MetricsThresholdAlert) -> None:
        self.alert = alert

    @property
    def threshold(self) -> float:
        if not (threshold_l := self.alert.get_alert().get("threshold")):
            raise RuntimeError("Expected key 'threshold' in alert definition retrieval")
        return threshold_l


class MetricRangeAlertDefinition:
    def __init__(self, alert: MetricsRangeAlert) -> None:
        self.alert = alert

    @property
    def range_low(self) -> float:
        if not (range_l := self.alert.get_alert().get("range_low")):
            raise RuntimeError("Expected key 'range_low' in alert definition retrieval")
        return range_l

    @property
    def range_high(self) -> float:
        if not (range_u := self.alert.get_alert().get("range_high")):
            raise RuntimeError(
                "Expected key 'range_high' in alert definition retrieval"
            )
        return range_u
