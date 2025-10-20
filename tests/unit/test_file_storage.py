import pytest
import time
import json
import uuid

from simvue.api.objects import FileStorage
from simvue.sender import sender

@pytest.mark.api
@pytest.mark.online
def test_create_file_storage_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = FileStorage.new(
        name=_uuid, disable_check=False, is_tenant_useable=False, is_default=False, is_enabled=False)
    _storage.commit()
    assert _storage.is_enabled == False
    assert _storage.name == _uuid
    assert _storage.is_default == False

    assert _storage.to_dict()
    _storage.delete()


@pytest.mark.api
@pytest.mark.offline
def test_create_file_storage_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = FileStorage.new(name=_uuid, disable_check=True, is_tenant_useable=False, is_default=False, offline=True, is_enabled=False)
    
    _storage.commit()
    assert _storage.name == _uuid
    assert _storage.is_enabled == False
    assert _storage.is_default == False
    
    with _storage._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("name") == _uuid
    assert _local_data.get("is_enabled") == False
    assert _local_data.get("is_default") == False
    
    _id_mapping = sender(_storage._local_staging_file.parents[1], 1, 10, ["storage"], throw_exceptions=True)
    time.sleep(1)
    _online_storage = FileStorage(_id_mapping.get(_storage.id))
    assert _online_storage.name == _uuid
    assert _online_storage.is_enabled == False
    assert _online_storage.is_default == False
    
    _online_storage.read_only(False)
    _online_storage.delete()