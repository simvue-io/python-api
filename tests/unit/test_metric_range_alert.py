import contextlib
import time
import pytest
import json
import uuid

from simvue.api.objects import MetricsRangeAlert, Alert

@pytest.mark.api
@pytest.mark.online
def test_metric_range_alert_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsRangeAlert.new(
        name=f"metrics_range_alert_{_uuid}",
        frequency=1,
        notification="none",
        metric="x",
        range_low=10,
        range_high=15,
        window=1,
        aggregation="average",
        rule="is inside range",
        description="a metric range alert"
    )
    _alert.commit()
    assert _alert.source == "metrics"
    assert _alert.alert.frequency == 1
    assert _alert.name == f"metrics_range_alert_{_uuid}"
    assert _alert.notification == "none"
    _alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_metric_range_alert_creation_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsRangeAlert.new(
        name=f"metrics_range_alert_{_uuid}",
        frequency=1,
        notification="none",
        metric="x",
        range_low=10,
        range_high=15,
        window=1,
        aggregation="average",
        rule="is inside range",
        offline=True
    )
    _alert.commit()
    assert _alert.source == "metrics"
    assert _alert.alert.frequency == 1
    assert _alert.name == f"metrics_range_alert_{_uuid}"
    assert _alert.notification == "none"
    _alert.delete()

    with _alert._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert not _local_data.get(_alert._label, {}).get(_alert.id)


@pytest.mark.api
@pytest.mark.online
def test_metric_range_alert_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsRangeAlert.new(
        name=f"metrics_range_alert_{_uuid}",
        frequency=1,
        notification="none",
        metric="x",
        range_low=10,
        range_high=15,
        window=1,
        aggregation="average",
        rule="is inside range",
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    _new_alert.read_only(False)
    assert isinstance(_new_alert, MetricsRangeAlert)
    _new_alert.read_only(False)
    _new_alert.description = "updated!"
    assert _new_alert.description != "updated!"
    _new_alert.commit()
    assert _new_alert.description == "updated!"
    _new_alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_metric_range_alert_modification_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsRangeAlert.new(
        name=f"metrics_range_alert_{_uuid}",
        frequency=1,
        notification="none",
        metric="x",
        range_low=10,
        range_high=15,
        window=1,
        aggregation="average",
        rule="is inside range",
        offline=True
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    assert isinstance(_new_alert, MetricsRangeAlert)
    _new_alert.description = "updated!"
    assert _new_alert.description != "updated!"
    _new_alert.commit()
    assert _new_alert.description == "updated!"
    _new_alert.delete()

@pytest.mark.api
@pytest.mark.online
def test_metric_range_alert_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = MetricsRangeAlert.new(
        name=f"metrics_range_alert_{_uuid}",
        frequency=1,
        notification="none",
        metric="x",
        range_low=10,
        range_high=15,
        window=1,
        aggregation="average",
        rule="is inside range"
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

