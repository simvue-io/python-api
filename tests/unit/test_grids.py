import typing
import datetime
import numpy
import numpy.testing as npt
import pytest
import uuid
import contextlib
import json
import time

from simvue.api.objects import Grid, GridMetrics, Folder, Run
from simvue.sender import Sender

@pytest.mark.api
@pytest.mark.online
def test_grid_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(name="hello", folder=_folder_name)
    _folder.commit()
    _run.commit()
    _grid_def=numpy.vstack([
        numpy.linspace(0, 10, 10),
        numpy.linspace(50, 60, 10),
    ])
    _grid_list = _grid_def.tolist()
    _grid = Grid.new(
        name=f"test_grid_creation_online_{_uuid}",
        labels=["x", "y"],
        grid=_grid_list
    )
    _grid.commit()
    _grid.attach_metric_for_run(_run.id, "A")
    # Get online version of grid
    _online_grid = Grid(_grid.id)
    npt.assert_array_equal(numpy.array(_online_grid.grid), _grid_def)
    _run.delete()
    with contextlib.suppress(RuntimeError):
        _grid.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_grid_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name="test_grid_creation_offline", folder=_folder_name, offline=True)
    _folder.commit()
    _run.commit()
    _grid_def=numpy.vstack([
        numpy.linspace(0, 10, 10),
        numpy.linspace(50, 60, 10),
    ])
    _grid_list = _grid_def.tolist()
    _grid = Grid.new(
        name=f"test_grid_creation_online_{_uuid}",
        grid=_grid_list,
        labels=["x", "y"],
        offline=True
    )
    _grid.commit()
    _grid.attach_metric_for_run(_run.id, "A")
    with _grid._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert _local_data.get("runs", [None])[0] == [_run.id, "A"]
    npt.assert_array_equal(numpy.array(_local_data.get("grid")), _grid_def)
    _sender = Sender(cache_directory=_grid._local_staging_file.parents[1], max_workers=1, threading_threshold=10, throw_exceptions=True)
    _sender.upload(["folders", "runs", "grids"])
    time.sleep(1)
    # Get online version of grid
    _online_grid = Grid(_sender.id_mapping.get(_grid.id))
    npt.assert_array_equal(numpy.array(_online_grid.grid), _grid_def)
    _grid.delete()
    with contextlib.suppress(RuntimeError):
        _online_grid.delete()
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.online
def test_grid_metrics_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(name="test_grid_metrics_creation_online", folder=_folder_name)
    _folder.commit()
    _run.status = "running"
    _values = {
        "x": 1,
        "y": 2.0,
        "z": True
    }
    _time: int = 0
    _step: int = 0
    _run.commit()
    _grid_def=numpy.vstack([
        numpy.linspace(0, 10, 10),
        numpy.linspace(50, 60, 10),
    ])
    _grid_list = _grid_def.tolist()
    _grid = Grid.new(
        name=f"test_grid_creation_online_{_uuid}",
        labels=["x", "y"],
        grid=_grid_list
    )
    _grid.commit()
    _grid.attach_metric_for_run(_run.id, "A")

    _metrics = GridMetrics.new(
        run=_run.id,
        data=[
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%f"
                ),
                "time": _time,
                "step": _step,
                "array": numpy.ones((10, 10)),
                "grid": _grid.id,
                "metric": "A"
            }
        ],
    )
    _metrics.commit()
    _run.status = "completed"
    _run.commit()
    time.sleep(1)
    # Online metrics
    assert list(GridMetrics.get(runs=[_run.id], metrics=["A"], step=_step))
    assert _grid.get_run_metric_values(run_id=_run.id, metric_name="A", step=_step)
    assert _grid.get_run_metric_span(run_id=_run.id, metric_name="A").get("max_timestamp")
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_grid_metrics_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name="test_grid_metrics_creation_offline", folder=_folder_name, offline=True)
    _run.status = "running"
    _time: int = 0
    _step: int = 0
    _folder.commit()
    _run.commit()
    _grid_def=numpy.vstack([
        numpy.linspace(0, 10, 10),
        numpy.linspace(50, 60, 10),
    ])
    _grid_list = _grid_def.tolist()
    _grid = Grid.new(
        name=f"test_grid_creation_offline_{_uuid}",
        labels=["x", "y"],
        grid=_grid_list,
        offline=True
    )
    _grid.commit()
    _grid.attach_metric_for_run(_run.id, "A")

    _metrics = GridMetrics.new(
        run=_run.id,
        data=[
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%f"
                ),
                "time": _time,
                "step": _step,
                "array": numpy.ones((10, 10)),
                "grid": _grid.id,
                "metric": "A"
            }
        ],
        offline=True
    )
    _metrics.commit()
    _run.status = "completed"
    _run.commit()
    _sender = Sender(cache_directory=_grid._local_staging_file.parents[1], max_workers=1, threading_threshold=10, throw_exceptions=True)
    _sender.upload(["folders", "runs", "grids", "grid_metrics"])
    time.sleep(1)
    # Online metrics
    assert list(GridMetrics.get(runs=[_sender.id_mapping[_run.id]], metrics=["A"], step=_step))
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)
