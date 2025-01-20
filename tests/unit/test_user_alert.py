import time
import json
import contextlib
import pytest
import uuid

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
        offline=True
    )
    _alert.commit()
    assert _alert.source == "user"
    assert _alert.name == f"users_alert_{_uuid}"
    assert _alert.notification == "none"
    _alert.delete()

    with _alert._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert not _local_data.get(_alert._label, {}).get(_alert.id)


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
        offline=True
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    assert isinstance(_new_alert, UserAlert)
    _new_alert.description = "updated!"

    with pytest.raises(AttributeError):
        assert _new_alert.description

    _new_alert.commit()
    assert _new_alert.description == "updated!"
    _new_alert.delete()

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

