import pytest
import time
import json
import uuid

from simvue.api.objects import FileStorage

@pytest.mark.api
def test_create_file_storage_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = FileStorage.new(name=_uuid, disable_check=False)
    _storage.commit()
    assert _storage.name == _uuid


@pytest.mark.api
def test_create_file_storage_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = FileStorage.new(name=_uuid, disable_check=False, offline=True)
    _storage.commit()
    assert _storage.name == _uuid
    _storage.delete()
