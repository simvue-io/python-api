import contextlib
import json
import pytest
import time
import datetime
import uuid

from simvue.api.objects import Events, Folder, Run
from simvue.models import DATETIME_FORMAT

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

