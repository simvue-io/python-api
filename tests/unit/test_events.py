import contextlib
import json
import pytest
import time
import datetime
import uuid

from simvue.api.objects import Events, Folder, Run
from simvue.models import DATETIME_FORMAT
from simvue.sender import sender

@pytest.mark.api
@pytest.mark.online
def test_events_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name)
    _folder.commit()
    _run.commit()
    _timestamp = datetime.datetime.now().strftime(DATETIME_FORMAT)
    _events =   Events.new(
        run=_run.id,
        events=[
            {"message": "This is a test!", "timestamp": _timestamp}
        ],
    )
    assert _events.to_dict()
    _events.commit()
    assert _events.get(run_id=_run.id)
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)

@pytest.mark.api
@pytest.mark.offline
def test_events_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(folder=_folder_name, offline=True)
    _folder.commit()
    _run.commit()
    _timestamp = datetime.datetime.now().strftime(DATETIME_FORMAT)
    _events =   Events.new(
        run=_run.id,
        events=[
            {"message": "This is a test!", "timestamp": _timestamp}
        ],
        offline=True
    )
    _events.commit()
    with _events._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
        
    assert _local_data.get("run") == _run.id
    assert _local_data.get("events")[0].get("message") == "This is a test!"
    assert _local_data.get("events")[0].get("timestamp") == _timestamp
    
    _id_mapping = sender(_events._local_staging_file.parents[1], 1, 10, ["folders", "runs", "events"], throw_exceptions=True)
    time.sleep(1)
    
    # Get online version of events
    _online_events = Events(_id_mapping.get(_events.id))
    _event_content = next(_online_events.get(run_id=_id_mapping.get(_run.id)))
    assert _event_content.message == "This is a test!"
    assert _event_content.timestamp == _timestamp

    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)