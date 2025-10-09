import contextlib
import json
import pytest
import time
import datetime
import uuid
from simvue.api.objects.run import RunBatchArgs
from simvue.sender import sender
from simvue.api.objects import Run, Metrics, Folder
from simvue.client import Client
from simvue.models import DATETIME_FORMAT
import logging
import pathlib
import requests

@pytest.mark.parametrize("retry_failed_uploads", (True, False))
@pytest.mark.parametrize("parallel", (True, False))

@pytest.mark.offline
def test_sender_exception_handling(offline_cache_setup, caplog, retry_failed_uploads, parallel):
    # Create something which will produce an error when sent, eg a metric with invalid run ID
    for i in range(5):
        _metrics = Metrics.new(
            run="invalid_run_id",
            metrics=[
                {
                    "timestamp": datetime.datetime.now().strftime(DATETIME_FORMAT),
                    "time": 1,
                    "step": 1,
                    "values": {"x": 1, "y": 2},
                }
            ],
            offline=True
        )
        _metrics.commit()
    
    with caplog.at_level(logging.ERROR):
        sender(threading_threshold=1 if parallel else 10)
            
    assert "Error while committing 'Metrics'" in caplog.text
    
    # Wait, then try sending again
    time.sleep(1)
    caplog.clear()
    
    with caplog.at_level(logging.ERROR):
        sender(retry_failed_uploads=retry_failed_uploads, threading_threshold=1 if parallel else 10)
        
    if retry_failed_uploads:
        assert "Error while committing 'Metrics'" in caplog.text
    else:
        assert not caplog.text
        
    # Check files not deleted
    _offline_metric_paths = list(pathlib.Path(offline_cache_setup.name).joinpath("metrics").iterdir())
    assert len(_offline_metric_paths) == 5
    # Check files have 'upload_failed: True'
    for _metric_path in _offline_metric_paths:
        with open(_metric_path, "r") as _file:
            _metric = json.load(_file)
            assert _metric.get("upload_failed") == True

@pytest.mark.parametrize("parallel", (True, False))
def test_sender_server_ids(offline_cache_setup, caplog, parallel):
    # Create an offline run
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path, offline=True)
    _folder.commit()
    
    _offline_run_ids = []
    
    for i in range(5):
        _name = f"test_sender_server_ids-{_uuid}-{i}"
        _run = Run.new(name=_name, folder=_path, offline=True)
        _run.commit()
        
        _offline_run_ids.append(_run.id)
        
        # Create metric associated with offline run ID
        _metrics = Metrics.new(
            run=_run.id,
            metrics=[
                {
                    "timestamp": datetime.datetime.now().strftime(DATETIME_FORMAT),
                    "time": 1,
                    "step": 1,
                    "values": {"x": i},
                }
            ],
            offline=True
        )
        _metrics.commit()
    
    # Send both items
    with caplog.at_level(logging.ERROR):
        sender(threading_threshold=1 if parallel else 10)
    
    assert not caplog.text
    
    # Check server ID mapping correctly created
    _online_runs = []
    for i, _offline_run_id in enumerate(_offline_run_ids):
        _id_file = pathlib.Path(offline_cache_setup.name).joinpath("server_ids", f"{_offline_run_id}.txt")
        assert _id_file.exists()
        _online_id = _id_file.read_text()
    
        # Check correct ID is contained within file
        _online_run = Run(identifier=_online_id)
        _online_runs.append(_online_run)
        assert _online_run.name == f"test_sender_server_ids-{_uuid}-{i}"
        
        # Check metric has been associated with correct online run
        _run_metric = next(_online_run.metrics)
        assert _run_metric[0] == 'x'
        assert _run_metric[1]["count"] == 1
        assert _run_metric[1]["min"] == i
    
        # Create a new offline metric with offline run ID
        _metrics = Metrics.new(
            run=_offline_run_id,
            metrics=[
                {
                    "timestamp": datetime.datetime.now().strftime(DATETIME_FORMAT),
                    "time": 2,
                    "step": 2,
                    "values": {"x": 2},
                }
            ],
            offline=True
        )
        _metrics.commit()
    
    # Run sender again, check online ID is correctly loaded from file and substituted for offline ID
    with caplog.at_level(logging.ERROR):
        sender(threading_threshold=1 if parallel else 10)
    
    assert not caplog.text
    
    # Check metric uploaded correctly
    for _online_run in _online_runs:
        _online_run.refresh()
        _run_metric = next(_online_run.metrics)
        assert _run_metric[0] == 'x'
        assert _run_metric[1]["count"] == 2
        
    # Check all files for runs and metrics deleted once they were processed
    assert len(list(pathlib.Path(offline_cache_setup.name).joinpath("runs").iterdir())) == 0
    assert len(list(pathlib.Path(offline_cache_setup.name).joinpath("metrics").iterdir())) == 0

@pytest.mark.parametrize("parallel", (True, False))
def test_send_heartbeat(offline_cache_setup, parallel, mocker):
    # Create an offline run
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path, offline=True)
    _folder.commit()
    
    _offline_runs = []
    
    for i in range(5):
        _name = f"test_sender_server_ids-{_uuid}-{i}"
        _run = Run.new(name=_name, folder=_path, offline=True, heartbeat_timeout=1, status="running")
        _run.commit()
        
        _offline_runs.append(_run)
    
    _id_mapping = sender(threading_threshold=1 if parallel else 10)
    _online_runs = [Run(identifier=_id_mapping.get(_offline_run.id)) for _offline_run in _offline_runs]
    assert all([_online_run.status == "running" for _online_run in _online_runs])
    
    spy_put = mocker.spy(requests, "put")
    
    # Create heartbeat and send every 0.5s for 5s
    for i in range(10):
        time.sleep(0.5)
        [_offline_run.send_heartbeat() for _offline_run in _offline_runs]
        sender(threading_threshold=1 if parallel else 10)
        
    # Check requests.put() endpoint called 50 times - once for each of the 5 runs, on all 10 iterations
    assert spy_put.call_count == 50
        
    # Get online runs and check all running
    [_online_run.refresh() for _online_run in _online_runs]
    assert all([_online_run.status == "running" for _online_run in _online_runs])