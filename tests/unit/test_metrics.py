import contextlib
import json
import pytest
import time
import datetime
import uuid

from simvue.api.objects import Metrics, Folder, Run

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
        run_id=_run.id,
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
    _metrics.commit()
    assert _metrics.get(metrics=["x", "y", "z"], xaxis="step")
    assert _metrics.span(run_ids=[_run.id])
    assert _metrics.names(run_ids=[_run.id])
    assert _metrics.to_dict()
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)

