import time
import contextlib
import pytest
import json
import uuid

from simvue.api.objects import MetricsThresholdAlert, Alert
from simvue.sender import sender

@pytest.mark.api
@pytest.mark.online
def test_metric_threshold_alert_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsThresholdAlert.new(
        name=f"metrics_threshold_alert_{_uuid}",
        frequency=1,
        notification="none",
        metric="x",
        threshold=10,
        window=1,
        rule="is above",
        aggregation="average",
        description="a metric threshold alert"
    )
    _alert.commit()
    assert _alert.source == "metrics"
    assert _alert.alert.frequency == 1
    assert _alert.name == f"metrics_threshold_alert_{_uuid}"
    assert _alert.notification == "none"
    _alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_metric_threshold_alert_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsThresholdAlert.new(
        name=f"metrics_threshold_alert_{_uuid}",
        frequency=1,
        notification="none",
        threshold=10,
        window=1,
        metric="x",
        rule="is above",
        aggregation="average",
        offline=True,
        description="a metric threshold alert"
    )
    _alert.commit()
    assert _alert.source == "metrics"
    assert _alert.alert.frequency == 1
    assert _alert.name == f"metrics_threshold_alert_{_uuid}"
    assert _alert.notification == "none"


    with _alert._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("source") == "metrics"
    assert _local_data.get("alert").get("frequency") == 1
    assert _local_data.get("name") == f"metrics_threshold_alert_{_uuid}"
    assert _local_data.get("notification") == "none"
    assert _local_data.get("alert").get("threshold") == 10
    
    sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"])
    time.sleep(1)
    
    # Get online ID and retrieve alert
    _online_id = _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").read_text()
    _online_alert = Alert(_online_id)
    
    assert _online_alert.source == "metrics"
    assert _online_alert.alert.frequency == 1
    assert _online_alert.name == f"metrics_threshold_alert_{_uuid}"
    assert _online_alert.alert.threshold == 10
    
    _online_alert.read_only(False)
    _online_alert.delete()
    _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").unlink()


@pytest.mark.api
@pytest.mark.online
def test_metric_threshold_alert_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsThresholdAlert.new(
        name=f"metrics_threshold_alert_{_uuid}",
        description="a metric threshold alert",
        frequency=1,
        notification="none",
        threshold=10,
        window=1,
        metric="x",
        rule="is above",
        aggregation="average",
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    assert isinstance(_new_alert, MetricsThresholdAlert)
    _new_alert.read_only(False)
    _new_alert.description = "updated!"
    assert _new_alert.description != "updated!"
    _new_alert.commit()
    assert _new_alert.description == "updated!"
    _new_alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_metric_threshold_alert_modification_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsThresholdAlert.new(
        name=f"metrics_threshold_alert_{_uuid}",
        frequency=1,
        notification="none",
        threshold=10,
        window=1,
        metric="x",
        rule="is above",
        aggregation="average",
        offline=True,
        description="a metric threshold alert"
    )
    _alert.commit()
    
    sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"])
    time.sleep(1) 
    
    # Get online ID and retrieve alert
    _online_id = _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").read_text()
    _online_alert = MetricsThresholdAlert(_online_id)
    
    assert _online_alert.source == "metrics"
    assert _online_alert.alert.frequency == 1
    assert _online_alert.name == f"metrics_threshold_alert_{_uuid}"
    assert _online_alert.alert.threshold == 10
      
    _new_alert = MetricsThresholdAlert(_alert.id)
    _new_alert.read_only(False)
    assert isinstance(_new_alert, MetricsThresholdAlert)
    _new_alert.description = "updated!"
    _new_alert.commit()
    
    # Since changes havent been sent, check online run not updated
    _online_alert.refresh()
    assert _online_alert.description != "updated!"
    
    with _alert._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("description") == "updated!"
    
    sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"])
    time.sleep(1) 
    
    _online_alert.refresh()
    assert _online_alert.description == "updated!"
    
    _online_alert.read_only(False)
    _online_alert.delete()
    _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").unlink()

@pytest.mark.api
@pytest.mark.online
def test_metric_range_alert_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsThresholdAlert.new(
        name=f"metrics_threshold_alert_{_uuid}",
        description="a metric threshold alert",
        frequency=1,
        notification="none",
        metric="x",
        threshold=10,
        window=1,
        rule="is above",
        aggregation="average"
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
