import typing
import datetime
import numpy
import pytest
import uuid
import contextlib
import json
import time
import os

from simvue.api.objects import Grid, GridMetrics, Folder, Run
from simvue.models import GridMetricSet
from simvue.run import Run as sv_Run
from simvue.sender import sender
from simvue.client import Client

@pytest.mark.api
@pytest.mark.online
def test_grid_creation_online(create_test_run: tuple[sv_Run, dict]) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _run, _ = create_test_run
    _grid = Grid.new(
        name=f"test_grid_creation_online_{_uuid}",
        grid=numpy.vstack([
            numpy.linspace(0, 10, 10),
            numpy.linspace(0, 20, 10),
            numpy.linspace(50, 60, 10),
        ]),
        labels=["x", "y", "z"]
    )
    _grid.commit()
    _grid.attach_to_run(_run.id)


@pytest.mark.api
@pytest.mark.online
def test_grid_metrics_creation_online(create_test_run: tuple[Run, dict]) -> None:
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
    _grid = Grid.new(
        name=f"test_grid_metrics_creation_online_{_uuid}",
        grid=numpy.vstack([
            numpy.linspace(0, 10, 10),
            numpy.linspace(0, 20, 10),
        ]),
        labels=["x", "y"]
    )
    _grid.commit()
    _grid.attach_to_run(_run.id)

    _metrics = GridMetrics.new(
        run=_run.id,
        metrics=[
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%f"
                ),
                "time": _time,
                "step": _step,
                "array": numpy.ones((10, 10)),
                "grid_identifier": _grid.id
            }
        ],
    )
    _metrics.commit()
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)

