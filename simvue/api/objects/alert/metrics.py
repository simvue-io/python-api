"""
Simvue Metric Alerts
====================

Classes for interacting with metric-based alerts either defined
locally or on a Simvue server

"""

import pydantic
import typing

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from simvue.api.objects.base import write_only
from .base import AlertBase, staging_check
from simvue.models import NAME_REGEX

Aggregate = typing.Literal["average", "sum", "at least one", "all"]
Rule = typing.Literal["is above", "is below", "is inside range", "is outside range"]

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035


class MetricsThresholdAlert(AlertBase):
    """
    Simvue Metrics Threshold Alert
    ==============================

    This class is used to connect to/create metrics threshold alert objects on the Simvue server,
    any modification of MetricsThresholdAlert instance attributes is mirrored on the remote object.

    """

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        """Initialise a Metrics Threshold Alert

        If an identifier is provided a connection will be made to the
        object matching the identifier on the target server.
        Else a new MetricsThresholdAlert instance will be created using arguments provided in kwargs.

        Parameters
        ----------
        identifier : str, optional
            the remote server unique id for the target folder
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        self.alert = MetricThresholdAlertDefinition(self)
        super().__init__(identifier, **kwargs)
        self._local_only_args += [
            "rule",
            "window",
            "metric",
            "threshold",
        ]

    @classmethod
    def get(
        cls, count: int | None = None, offset: int | None = None
    ) -> dict[str, typing.Any]:
        """Retrieve only MetricsThresholdAlerts"""
        raise NotImplementedError("Retrieve of only metric alerts is not yet supported")

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        metric: str,
        description: str | None,
        notification: typing.Literal["none", "email"],
        aggregation: Aggregate,
        rule: typing.Literal["is above", "is below"],
        window: pydantic.PositiveInt,
        threshold: float | int,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        offline: bool = False,
        **_,
    ) -> Self:
        """Create a new metric threshold alert either locally or on the server

        Note all arguments are keyword arguments.

        Parameters
        ----------
        name : str
            name to assign to this alert
        description : str | None
            description for this alert
        metric : str
            the metric to monitor, or a globular expression to match multiple metrics
        notification : "none" | "email"
            the notification settings for this alert
        aggregation : "average" | "sum" | "at least one" | "all"
            how to aggregate metric values to deduce if alert is triggered
        rule : "is above" | "is below"
            threshold condition
        window : int
            window over which to calculate aggregation
        threshold : float | int
            the value defining the threshold
        frequency : int
            how often to monitor the metric
        enabled : bool, optional
            whether this alert is enabled upon creation, default is True
        offline : bool, optional
            whether to create the alert locally, default is False

        """
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
            description=description,
            notification=notification,
            source="metrics",
            alert=_alert_definition,
            enabled=enabled,
            _read_only=False,
            _offline=offline,
        )
        _alert._staging |= _alert_definition
        _alert._params = {"deduplicate": True}

        return _alert

    @override
    def __eq__(self, other: "AlertBase") -> bool:
        if not isinstance(other, MetricsThresholdAlert):
            return False
        return super().__eq__(other) and self.alert == other.alert


class MetricsRangeAlert(AlertBase):
    """
    Simvue Metrics Range Alert
    ==========================

    This class is used to connect to/create metrics range alert objects on the Simvue server,
    any modification of MetricsRangeAlert instance attributes is mirrored on the remote object.

    """

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        """Initialise a Metrics Range Alert

        If an identifier is provided a connection will be made to the
        object matching the identifier on the target server.
        Else a new MetricsRangeAlert instance will be created using arguments provided in kwargs.

        Parameters
        ----------
        identifier : str, optional
            the remote server unique id for the target folder
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        self.alert = MetricRangeAlertDefinition(self)
        super().__init__(identifier, **kwargs)
        self._local_only_args += [
            "rule",
            "window",
            "metric",
            "range_low",
            "range_high",
        ]

    @override
    def __eq__(self, other: "AlertBase") -> bool:
        """Compare two MetricRangeAlerts"""
        if not isinstance(other, MetricsRangeAlert):
            return False
        return super().__eq__(other) and self.alert == other.alert

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        metric: str,
        description: str | None,
        notification: typing.Literal["none", "email"],
        aggregation: Aggregate,
        rule: typing.Literal["is inside range", "is outside range"],
        window: pydantic.PositiveInt,
        range_high: float,
        range_low: float,
        frequency: pydantic.PositiveInt,
        enabled: bool = True,
        offline: bool = False,
        **_,
    ) -> Self:
        """Create a new metric range alert either locally or on the server

        Note all arguments are keyword arguments.

        Parameters
        ----------
        name : str
            name to assign to this alert
        metric : str
            the metric to monitor
        description : str | None
            description for this alert
        notification : "none" | "email"
            the notification settings for this alert
        aggregation : "average" | "sum" | "at least one" | "all"
            how to aggregate metric values to deduce if alert is triggered
        rule : "is inside range" | "is outside range"
            threshold condition
        window : int
            window over which to calculate aggregation
        range_high : float | int
            the value defining the upper limit
        range_low : float | int
            the value defining the lower limit
        frequency : int | None
            how often to monitor the metric
        enabled : bool, optional
            whether this alert is enabled upon creation, default is True
        offline : bool, optional
            whether to create the alert locally, default is False

        """
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
        _alert = MetricsRangeAlert(
            name=name,
            description=description,
            notification=notification,
            source="metrics",
            enabled=enabled,
            alert=_alert_definition,
            _read_only=False,
            _offline=offline,
        )
        _alert._staging |= _alert_definition
        _alert._params = {"deduplicate": True}
        return _alert


class MetricsAlertDefinition:
    """General alert definition for a metric alert"""

    def __init__(self, alert: MetricsRangeAlert) -> None:
        """Initialise definition with target alert"""
        self._sv_obj = alert

    def __eq__(self, other: "MetricsAlertDefinition") -> bool:
        """Compare a MetricsAlertDefinition with another"""
        return all(
            [
                self.aggregation == other.aggregation,
                self.frequency == other.frequency,
                self.rule == other.rule,
                self.window == other.window,
            ]
        )

    @property
    def aggregation(self) -> Aggregate:
        """Retrieve the aggregation strategy for this alert"""
        if (_aggregation := self._sv_obj.get_alert().get("aggregation")) is None:
            raise RuntimeError(
                "Expected key 'aggregation' in alert definition retrieval"
            )
        return _aggregation

    @property
    def rule(self) -> Rule:
        """Retrieve the rule for this alert"""
        if (_rule := self._sv_obj.get_alert().get("rule")) is None:
            raise RuntimeError("Expected key 'rule' in alert definition retrieval")
        return _rule

    @property
    def window(self) -> int:
        """Retrieve the aggregation window for this alert"""
        if (_window := self._sv_obj.get_alert().get("window")) is None:
            raise RuntimeError("Expected key 'window' in alert definition retrieval")
        return _window

    @property
    @staging_check
    def frequency(self) -> int:
        """Retrieve the monitor frequency for this alert"""
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
        """Set the monitor frequency for this alert"""
        _alert = self._sv_obj.get_alert() | {"frequency": frequency}
        self._sv_obj._staging["alert"] = _alert


class MetricThresholdAlertDefinition(MetricsAlertDefinition):
    """Alert definition for metric threshold alerts"""

    def __eq__(self, other: "MetricThresholdAlertDefinition") -> bool:
        """Compare this MetricThresholdAlertDefinition with another"""
        if not super().__eq__(other):
            return False

        return self.threshold == other.threshold

    @property
    def threshold(self) -> float:
        """Retrieve the threshold value for this alert"""
        if (threshold_l := self._sv_obj.get_alert().get("threshold")) is None:
            raise RuntimeError("Expected key 'threshold' in alert definition retrieval")
        return threshold_l


class MetricRangeAlertDefinition(MetricsAlertDefinition):
    """Alert definition for metric range alerts"""

    def __eq__(self, other: "MetricRangeAlertDefinition") -> bool:
        """Compare a MetricRangeAlertDefinition with another"""
        if not super().__eq__(other):
            return False

        return all(
            [
                self.range_high == other.range_high,
                self.range_low == other.range_low,
            ]
        )

    @property
    def range_low(self) -> float:
        """Retrieve the lower limit for metric range"""
        if (range_l := self._sv_obj.get_alert().get("range_low")) is None:
            raise RuntimeError("Expected key 'range_low' in alert definition retrieval")
        return range_l

    @property
    def range_high(self) -> float:
        """Retrieve upper limit for metric range"""
        if (range_u := self._sv_obj.get_alert().get("range_high")) is None:
            raise RuntimeError(
                "Expected key 'range_high' in alert definition retrieval"
            )
        return range_u
