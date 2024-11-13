import pydantic
import typing
from .base import AlertBase, staging_check
from simvue.models import NAME_REGEX

Aggregate = typing.Literal["average", "sum", "at least one", "all"]
Rule = typing.Literal["is above", "is below", "is inside range", "is outside range"]


class MetricsThresholdAlert(AlertBase):
    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        self.alert = MetricThresholdAlertDefinition(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        metric: str,
        notification: typing.Literal["none", "email"],
        aggregation: Aggregate,
        rule: Rule,
        window: pydantic.PositiveInt,
        threshold: float,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        tags: list[str] | None = None,
        offline: bool = False,
    ) -> typing.Self:
        _alert_definition = {
            "rule": rule,
            "frequency": frequency,
            "window": window,
            "metric": metric,
            "aggregation": aggregation,
            "threshold": threshold,
        }
        _alert = MetricsThresholdAlert(
            name=name,
            notification=notification,
            source="metrics",
            alert=_alert_definition,
            enabled=enabled,
            tags=tags or [],
        )
        _alert.offline_mode(offline)
        return _alert


class MetricsRangeAlert(AlertBase):
    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        self.alert = MetricRangeAlertDefinition(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        metric: str,
        notification: typing.Literal["none", "email"],
        aggregation: Aggregate,
        rule: Rule,
        window: pydantic.PositiveInt,
        range_high: float,
        range_low: float,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        tags: list[str] | None = None,
        offline: bool = False,
    ) -> typing.Self:
        if range_low >= range_high:
            raise ValueError(f"Invalid arguments for range [{range_low}, {range_high}]")

        _alert_definition = {
            "rule": rule,
            "frequency": frequency,
            "window": window,
            "metric": metric,
            "aggregation": aggregation,
            "range_low": range_low,
            "range_high": range_high,
        }
        _alert = MetricsThresholdAlert(
            name=name,
            notification=notification,
            source="metrics",
            tags=tags or [],
            enabled=enabled,
            alert=_alert_definition,
        )
        _alert.offline_mode(offline)
        return _alert


class MetricsAlertDefinition:
    def __init__(self, alert: MetricsRangeAlert) -> None:
        self._sv_obj = alert

    @property
    def aggregation(self) -> Aggregate:
        if not (_aggregation := self._sv_obj.get_alert().get("aggregation")):
            raise RuntimeError(
                "Expected key 'aggregation' in alert definition retrieval"
            )
        return _aggregation

    @property
    def rule(self) -> Rule:
        if not (_rule := self._sv_obj.get_alert().get("rule")):
            raise RuntimeError("Expected key 'rule' in alert definition retrieval")
        return _rule

    @property
    def window(self) -> int:
        if not (_window := self._sv_obj.get_alert().get("window")):
            raise RuntimeError("Expected key 'window' in alert definition retrieval")
        return _window

    @property
    @staging_check
    def frequency(self) -> int:
        try:
            return self._sv_obj.get_alert()["frequency"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @frequency.setter
    @pydantic.validate_call
    def frequency(self, frequency: int) -> None:
        _alert = self._sv_obj.get_alert() | {"frequency": frequency}
        self._sv_obj._staging["alert"] = _alert


class MetricThresholdAlertDefinition(MetricsAlertDefinition):
    @property
    def threshold(self) -> float:
        if not (threshold_l := self._sv_obj.get_alert().get("threshold")):
            raise RuntimeError("Expected key 'threshold' in alert definition retrieval")
        return threshold_l


class MetricRangeAlertDefinition(MetricsAlertDefinition):
    @property
    def range_low(self) -> float:
        if not (range_l := self._sv_obj.get_alert().get("range_low")):
            raise RuntimeError("Expected key 'range_low' in alert definition retrieval")
        return range_l

    @property
    def range_high(self) -> float:
        if not (range_u := self._sv_obj.get_alert().get("range_high")):
            raise RuntimeError(
                "Expected key 'range_high' in alert definition retrieval"
            )
        return range_u
