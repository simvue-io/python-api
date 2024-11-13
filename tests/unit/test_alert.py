import time
import pytest
import uuid

from simvue.api.objects import Alert, MetricsRangeAlert, MetricsThresholdAlert, EventsAlert

@pytest.mark.api
def test_event_alert_creation() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none"
    )
    _alert.commit()
    assert _alert.alert.frequency == 1
    assert _alert.alert.pattern == "completed"
    assert _alert.name == f"events_alert_{_uuid}"
    assert _alert.notification == "none"


@pytest.mark.api
def test_event_alert_modification() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none"
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    assert isinstance(_new_alert, EventsAlert)
    _new_alert.description = "updated!"
    assert _new_alert.description != "updated!"
    _new_alert.commit()
    assert _new_alert.description == "updated!"
