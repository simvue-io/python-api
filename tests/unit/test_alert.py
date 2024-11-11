import pytest
import uuid

from simvue.api.objects import SimvueAlert, MetricsRangeAlert, MetricsThresholdAlert, EventsAlert

@pytest.mark.api
def test_event_alert_creation() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none"
    )
    assert _alert.alert.frequency == 1
    assert _alert.alert.pattern == "completed"
    assert _alert.name == f"events_alert_{_uuid}"
    assert _alert.notification == "none"
