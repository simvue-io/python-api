import pytest
import time
import contextlib
import json
import uuid

from simvue.api.objects.administrator import User, Tenant
from simvue.sender import sender

@pytest.mark.api
@pytest.mark.online
def test_create_user_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tenant = Tenant.new(name=_uuid)
    try:
        _tenant.commit()
    except RuntimeError as e:
        assert "You do not have permission" in str(e)
        return
    _user = User.new(
        username="jbloggs",
        fullname="Joe Bloggs",
        email="jbloggs@simvue.io",
        is_manager=False,
        is_admin=False,
        is_readonly=True,
        welcome=False,
        tenant=_tenant.id
    )
    _user.commit()
    time.sleep(1)
    _new_user = User(_user.id)
    assert _new_user.username == "jbloggs"
    assert _new_user.enabled
    _new_user.delete()
    _tenant.delete()


@pytest.mark.api
@pytest.mark.offline
def test_create_user_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _user = User.new(
        username="jbloggs",
        fullname="Joe Bloggs",
        email="jbloggs@simvue.io",
        is_manager=False,
        is_admin=False,
        is_readonly=True,
        welcome=False,
        tenant=_uuid,
        offline=True
    )
    _user.commit()
    assert _user.username == "jbloggs"
    assert _user.fullname == "Joe Bloggs"
    assert _user.email == "jbloggs@simvue.io"
    
    with _user._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("username") == "jbloggs"
    assert _local_data.get("fullname") == "Joe Bloggs"
    assert _local_data.get("email") == "jbloggs@simvue.io"

    _id_mapping = sender(_user._local_staging_file.parents[1], 1, 10, ["users"], throw_exceptions=True)
    time.sleep(1)
    _online_user = User(_id_mapping.get(_user.id))
    assert _online_user.username == "jbloggs"
    assert _online_user.fullname == "Joe Bloggs"
    assert _online_user.email == "jbloggs@simvue.io"
    
    _online_user.read_only(False)
    _online_user.delete()
    
@pytest.mark.api
@pytest.mark.online
def test_user_get_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tenant = Tenant.new(name=_uuid)
    try:
        _tenant.commit()
    except RuntimeError as e:
        assert "You do not have permission" in str(e)
        return
    _user = User.new(
        username="jbloggs",
        fullname="Joe Bloggs",
        email="jbloggs@simvue.io",
        is_manager=False,
        is_admin=False,
        is_readonly=True,
        welcome=False,
        tenant=_tenant.id
    )
    _user.commit()
    _failed = []

    for member in _user._properties:
        try:
            getattr(_user, member)
        except Exception as e:
            _failed.append((member, f"{e}"))
    with contextlib.suppress(Exception):
        _user.delete()
        _tenant.delete()

    if _failed:
        raise AssertionError("\n" + "\n\t- ".join(": ".join(i) for i in _failed))
