from .events import EventsAlert
from .metrics import MetricsThresholdAlert, MetricsRangeAlert
from .base import AlertBase


class SimvueAlert:
    def __new__(
        cls, identifier: str | None = None, **kwargs
    ) -> EventsAlert | MetricsRangeAlert | MetricsThresholdAlert:
        _alert_pre = AlertBase(identifier)
        if _alert_pre.source == "events":
            return EventsAlert(identifier)
        elif _alert_pre.source == "metrics" and _alert_pre.get_alert().get("threshold"):
            return MetricsThresholdAlert(identifier)
        elif _alert_pre.source == "metrics":
            return MetricsRangeAlert(identifier)
