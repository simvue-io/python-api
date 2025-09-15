import contextlib
import json
import pytest
import time
import datetime
import uuid

from simvue.api.objects import Metrics, Folder, Run
from simvue.models import DATETIME_FORMAT
from simvue.sender import sender

@pytest.mark.api
@pytest.mark.online
def test_metrics_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name)
    _values = {
        "x": 1,
        "y": 2.0,
        "z": True
    }
    _time: int = 1
    _step: int = 1
    _folder.commit()
    _run.commit()
    _metrics = Metrics.new(
        run=_run.id,
        metrics=[
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%f"
                ),
                "time": _time,
                "step": _step,
                "values": _values,
            }
        ],
    )
    assert _metrics.to_dict()
    _metrics.commit()
    _data = next(_metrics.get(metrics=["x", "y", "z"], runs=[_run.id], xaxis="step"))
    assert sorted(_metrics.names(run_ids=[_run.id])) == sorted(_values.keys())
    assert _data.get(_run.id).get('y')[0].get('value') == 2.0
    assert _data.get(_run.id).get('y')[0].get('step') == 1
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_metrics_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name="test_metrics_creation_offline", folder=_folder_name, offline=True)
    _folder.commit()
    _run.commit()
    
    _values = {
        "x": 1,
        "y": 2.0,
        "z": True
    }
    _time: int = 1
    _step: int = 1
    _timestamp = datetime.datetime.now().strftime(DATETIME_FORMAT)
    _metrics = Metrics.new(
        run=_run.id,
        metrics=[
            {
                "timestamp": _timestamp,
                "time": _time,
                "step": _step,
                "values": _values,
            }
        ],
        offline=True
    )
    _metrics.commit()
    with _metrics._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert _local_data.get("run") == _run.id
    assert _local_data.get("metrics")[0].get("values") == _values
    assert _local_data.get("metrics")[0].get("timestamp") == _timestamp
    assert _local_data.get("metrics")[0].get("step") == _step
    assert _local_data.get("metrics")[0].get("time") == _time

    _id_mapping = sender(_metrics._local_staging_file.parents[1], 1, 10, ["folders", "runs", "metrics"])
    time.sleep(1)

    # Get online version of metrics
    _online_metrics = Metrics(_id_mapping.get(_metrics.id))
    _data = next(_online_metrics.get(metrics=["x", "y", "z"], runs=[_id_mapping.get(_run.id)], xaxis="step"))
    assert sorted(_online_metrics.names(run_ids=[_id_mapping.get(_run.id)])) == sorted(_values.keys())
    assert _data.get(_id_mapping.get(_run.id)).get('y')[0].get('value') == 2.0
    assert _data.get(_id_mapping.get(_run.id)).get('y')[0].get('step') == 1
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)
