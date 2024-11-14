import pytest
import time
import json
import uuid

from simvue.api.objects.administrator import Tenant


@pytest.mark.api
def test_create_tenant_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tenant = Tenant.new(name=_uuid)
    try:
        _tenant.commit()
    except RuntimeError as e:
        assert "You do not have permission" in str(e)
        return
    time.sleep(1)
    _new_tenant = Tenant(_tenant.id)
    assert _new_tenant.name == _uuid
    assert _new_tenant.enabled
    _new_tenant.delete()


@pytest.mark.api
def test_create_tenant_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _tenant = Tenant.new(name=_uuid, offline=True)
    _tenant.commit()
    time.sleep(1)
    _new_tenant = Tenant(_tenant.id)
    assert _new_tenant.name == _uuid
    assert _new_tenant.enabled
    _new_tenant.delete()
