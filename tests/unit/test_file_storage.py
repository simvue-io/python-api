import pytest
import time
import json
import uuid

from simvue.api.objects import FileStorage

@pytest.mark.api
@pytest.mark.online
def test_create_file_storage_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = FileStorage.new(
        name=_uuid, disable_check=False, tenant_usable=False, default=False, enabled=True)
    _storage.commit()
    assert _storage.enabled
    assert _storage.name == _uuid
    _storage.delete()


@pytest.mark.api
@pytest.mark.offline
def test_create_file_storage_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = FileStorage.new(name=_uuid, disable_check=False, tenant_usable=False, default=False, offline=True)
    _storage.commit()
    assert _storage.name == _uuid
    _storage.delete()
