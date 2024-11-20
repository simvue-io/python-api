import time
import json
import pytest
import uuid

from simvue.api.objects import Alert, UserAlert

@pytest.mark.api
def test_user_alert_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none"
    )
    _alert.commit()
    assert _alert.source == "user"
    assert _alert.name == f"users_alert_{_uuid}"
    assert _alert.notification == "none"
    assert dict(Alert.get())
    _alert.delete()


@pytest.mark.api
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
def test_user_alert_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _alert = UserAlert.new(
        name=f"users_alert_{_uuid}",
        notification="none",
    )
    _alert.commit()
    time.sleep(1)
    _new_alert = Alert(_alert.id)
    assert isinstance(_new_alert, UserAlert)
    _new_alert.description = "updated!"
    assert _new_alert.description != "updated!"
    _new_alert.commit()
    assert _new_alert.description == "updated!"
    _new_alert.delete()


@pytest.mark.api
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

