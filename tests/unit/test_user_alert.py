import time
import json
import contextlib
import pytest
import uuid
from simvue.sender import sender
from simvue.api.objects import Alert, UserAlert, Run
from simvue.api.objects.folder import Folder

@pytest.mark.api
@pytest.mark.online
def test_user_alert_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
        description=None
    )
    _alert.commit()
    assert _alert.source == "user"
    assert _alert.name == f"users_alert_{_uuid}"
    assert _alert.notification == "none"
    assert dict(Alert.get())
    _alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_user_alert_creation_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
        offline=True,
        description = "test user alert"
    )
    _alert.commit()
    assert _alert.source == "user"
    assert _alert.name == f"users_alert_{_uuid}"
    assert _alert.notification == "none"

    with _alert._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert _local_data.get("source") == "user"
    assert _local_data.get("name") == f"users_alert_{_uuid}"
    assert _local_data.get("notification") == "none"

    _id_mapping = sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"])
    time.sleep(1)
    
    _online_id = _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").read_text()
    _online_alert = Alert(_online_id)
    
    assert _online_alert.source == "user"
    assert _online_alert.name == f"users_alert_{_uuid}"
    assert _online_alert.notification == "none"
    
    _online_alert.read_only(False)
    _online_alert.delete()
    _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").unlink()

        
@pytest.mark.api
@pytest.mark.online
def test_user_alert_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
        description=None
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    assert isinstance(_new_alert, UserAlert)
    _new_alert.read_only(False)
    _new_alert.description = "updated!"
    assert _new_alert.description != "updated!"
    _new_alert.commit()
    assert _new_alert.description == "updated!"
    _new_alert.delete()


@pytest.mark.api
@pytest.mark.offline
def test_user_alert_modification_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
        offline=True,
        description = "test user alert"
    )
    _alert.commit()
    
    sender(_alert._local_staging_file.parents[1], 1, 10, ["alerts"])
    time.sleep(1) 
    
    # Get online ID and retrieve alert
    _online_id = _alert._local_staging_file.parents[1].joinpath("server_ids", f"{_alert._local_staging_file.name.split('.')[0]}.txt").read_text()
    _online_alert = UserAlert(_online_id)
    
    assert _online_alert.source == "user"
    assert _online_alert.name == f"users_alert_{_uuid}"
    assert _online_alert.notification == "none"
    
    _new_alert = UserAlert(_alert.id)
    _new_alert.read_only(False)
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
def test_user_alert_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
        description=None
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


@pytest.mark.api
@pytest.mark.online
def test_user_alert_status() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
        description=None
    )
    _alert.commit()
    _folder = Folder.new(path=f"/simvue_unit_tests/{_uuid}")
    _run = Run.new(folder=f"/simvue_unit_tests/{_uuid}")
    _folder.commit()
    _run.alerts = [_alert.id]
    _run.commit()
    _alert.set_status(_run.id, "critical")
    time.sleep(1)
    _run.delete()
    _folder.delete(recursive=True, runs_only=False, delete_runs=True)
    _alert.delete()
    
    
@pytest.mark.api
@pytest.mark.offline
def test_user_alert_status_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
        description=None,
        offline=True
    )
    _alert.commit()
    _folder = Folder.new(path=f"/simvue_unit_tests/{_uuid}", offline=True)
    _run = Run.new(folder=f"/simvue_unit_tests/{_uuid}", offline=True)
    _folder.commit()
    _run.alerts = [_alert.id]
    _run.commit()

    sender(_alert._local_staging_file.parents[1], 1, 10, ["folders", "runs", "alerts"])
    time.sleep(1) 

    _alert.set_status(_run.id, "critical")
    _alert.commit()
    import pdb; pdb.set_trace()
    time.sleep(1)
    _run.delete()
    _folder.delete(recursive=True, runs_only=False, delete_runs=True)
    _alert.delete()

