"""
Simvue Alert Retrieval
======================

To simplify case whereby user does not know the alert type associated
with an identifier, use a generic alert object.
"""

from .events import EventsAlert
from .metrics import MetricsThresholdAlert, MetricsRangeAlert
from .base import AlertBase


class Alert:
    """Generic Simvue alert retrieval class"""

    def __new__(cls, identifier: str | None = None, **kwargs):
        """Retrieve an object representing an alert either locally or on the server by id"""
        _alert_pre = AlertBase(identifier)
        if _alert_pre.source == "events":
            return EventsAlert(identifier)
        elif _alert_pre.source == "metrics" and _alert_pre.get_alert().get("threshold"):
            return MetricsThresholdAlert(identifier)
        elif _alert_pre.source == "metrics":
            return MetricsRangeAlert(identifier)

        raise RuntimeError(f"Unknown source type '{_alert_pre.source}'")
