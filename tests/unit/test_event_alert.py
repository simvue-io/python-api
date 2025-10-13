import time
import json
import pytest
import contextlib
import uuid

from simvue.api.objects import Alert, EventsAlert
from simvue.sender import sender

@pytest.mark.api
@pytest.mark.online
def test_event_alert_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none",
        description=None
    )
    _alert.commit()
    assert _alert.source == "events"
    assert _alert.alert.frequency == 1
    assert _alert.alert.pattern == "completed"
    assert _alert.name == f"events_alert_{_uuid}"
    assert _alert.notification == "none"
    assert _alert.to_dict()
    _alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_event_alert_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none",
        offline=True,
        description=None
    )

    _alert.commit()
    assert _alert.source == "events"
    assert _alert.alert.frequency == 1
    assert _alert.alert.pattern == "completed"
    assert _alert.name == f"events_alert_{_uuid}"
    assert _alert.notification == "none"
    
    with _alert._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("source") == "events"
    assert _local_data.get("alert").get("frequency") == 1
    assert _local_data.get("alert").get("pattern") == "completed"
    assert _local_data.get("name") == f"events_alert_{_uuid}"
    assert _local_data.get("notification") == "none"
    
    _id_mapping = sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"], throw_exceptions=True)
    time.sleep(1)
    
    # Get online ID and retrieve alert
    _online_alert = Alert(_id_mapping.get(_alert.id))
    assert _online_alert.source == "events"
    assert _online_alert.alert.frequency == 1
    assert _online_alert.alert.pattern == "completed"
    assert _online_alert.name == f"events_alert_{_uuid}"
    assert _online_alert.notification == "none"

    _alert.delete()
    _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").unlink()

@pytest.mark.api
@pytest.mark.online
def test_event_alert_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none",
        description=None
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    _new_alert.read_only(False)
    assert isinstance(_new_alert, EventsAlert)
    _new_alert.description = "updated!"
    assert _new_alert.description != "updated!"
    _new_alert.commit()
    assert _new_alert.description == "updated!"
    _new_alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_event_alert_modification_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none",
        offline=True,
        description=None
    )
    _alert.commit()
    _id_mapping = sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"], throw_exceptions=True)
    time.sleep(1)  
      
    # Get online ID and retrieve alert
    _online_alert = Alert(_id_mapping.get(_alert.id))
    assert _online_alert.source == "events"
    assert _online_alert.alert.frequency == 1
    assert _online_alert.alert.pattern == "completed"
    assert _online_alert.name == f"events_alert_{_uuid}"
    assert _online_alert.notification == "none"
    
    _new_alert = EventsAlert(_alert.id)
    _new_alert.read_only(False)
    _new_alert.description = "updated!"
    _new_alert.commit()

    # Since changes havent been sent, check online run not updated
    _online_alert.refresh()
    assert _online_alert.description != "updated!"
    
    with _alert._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("description") == "updated!"
    
    sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"], throw_exceptions=True)
    time.sleep(1)
    
    _online_alert.refresh()
    assert _online_alert.description == "updated!"
    
    _online_alert.read_only(False)
    _online_alert.delete()
    _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").unlink()


@pytest.mark.api
@pytest.mark.online
def test_event_alert_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = EventsAlert.new(
        name=f"events_alert_{_uuid}",
        frequency=1,
        pattern="completed",
        notification="none",
        description="event_alert prop alert"
    )
    _alert.commit()

    _failed = []

    for member in _alert._properties:
        try:
            getattr(_alert, member)
        except Exception as e:
            _failed.append((member, f"{e}"))
    with contextlib.suppress(Exception):
        _alert.delete()

    if _failed:
        raise AssertionError("\n" + "\n\t- ".join(": ".join(i) for i in _failed))

