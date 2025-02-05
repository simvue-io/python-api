import pytest
import time
import json
import uuid

from simvue.api.objects import S3Storage
from simvue.api.objects.storage.fetch import Storage
from simvue.sender import sender

@pytest.mark.api
@pytest.mark.online
def test_create_s3_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _failed = []
    _storage = S3Storage.new(
        name=_uuid,
        endpoint_url="https://not-a-real-url.io",
        disable_check=True,
        is_tenant_useable=False,
        is_default=False,
        region_name="fictionsville",
        access_key_id="dummy_key",
        secret_access_key="not_a_key",
        bucket="dummy_bucket",
        is_enabled=False
    )
    _storage.commit()
    for member in _storage._properties:
        try:
            getattr(_storage, member)
        except Exception as e:
            _failed.append((member, f"{e}"))
    assert _storage.to_dict()
    assert _storage.name == _uuid
    assert _storage.config.endpoint_url == "https://not-a-real-url.io/"
    assert _storage.config.region_name == "fictionsville"
    assert _storage.config.bucket == "dummy_bucket"
    assert _storage.created
    assert dict(Storage.get())
    _storage.delete()
    if _failed:
        raise AssertionError("\n\t-" + "\n\t- ".join(": ".join(i) for i in _failed))


@pytest.mark.api
@pytest.mark.offline
def test_create_s3_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = S3Storage.new(
        name=_uuid,
        endpoint_url="https://not-a-real-url.io",
        disable_check=True,
        region_name="fictionsville",
        access_key_id="dummy_key",
        secret_access_key="not_a_key",
        bucket="dummy_bucket",
        is_default=False,
        is_tenant_useable=False,
        is_enabled=False,
        offline=True
    )
    _storage.commit()
    with _storage._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("name") == _uuid
    assert _local_data.get("config").get("endpoint_url") == "https://not-a-real-url.io/"
    assert _local_data.get("config").get("region_name") == "fictionsville"
    assert _local_data.get("config").get("bucket") == "dummy_bucket"
    assert _local_data.get("is_enabled") == False
    assert not _local_data.get("status", None)
    assert not _local_data.get("user", None)
    assert not _local_data.get("usage", None)

    _id_mapping = sender(_storage._local_staging_file.parents[1], 1, 10, ["storage"])
    _online_id = _id_mapping[_storage.id]
    time.sleep(1)
    
    _online_storage = S3Storage(_online_id)
    
    assert _online_storage.name == _uuid
    assert _online_storage.is_enabled == False
    assert _online_storage.config.endpoint_url == "https://not-a-real-url.io/"
    assert _online_storage.config.region_name == "fictionsville"
    assert _online_storage.config.bucket == "dummy_bucket"
    
    _online_storage.read_only(False)
    _online_storage.delete()
    
    
    
        

    
