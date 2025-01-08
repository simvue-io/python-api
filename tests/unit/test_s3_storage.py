import pytest
import time
import json
import uuid

from simvue.api.objects import S3Storage
from simvue.api.objects.storage.fetch import Storage

@pytest.mark.api
@pytest.mark.online
def test_create_s3_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = S3Storage.new(
        name=_uuid,
        endpoint_url="https://not_a_real_url.io",
        disable_check=True,
        tenant_usable=False,
        default=False,
        region_name="fictionsville",
        access_key_id="dummy_key",
        secret_access_key="not_a_key",
        bucket="dummy_bucket"
    )
    _storage.commit()
    assert _storage.name == _uuid
    assert _storage.config.endpoint_url == "https://not_a_real_url.io/"
    assert _storage.config.region_name == "fictionsville"
    assert _storage.config.bucket == "dummy_bucket"
    assert _storage.created
    assert dict(Storage.get())
    _storage.delete()


@pytest.mark.api
@pytest.mark.offline
def test_create_s3_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = S3Storage.new(
        name=_uuid,
        endpoint_url="https://not_a_real_url.io",
        disable_check=False,
        region_name="fictionsville",
        access_key_id="dummy_key",
        secret_access_key="not_a_key",
        bucket="dummy_bucket",
        default=False,
        tenant_usable=False,
        offline=True
    )
    _storage.commit()
    assert _storage.name == _uuid
    assert _storage.config.endpoint_url == "https://not_a_real_url.io"
    assert _storage.config.region_name == "fictionsville"
    assert _storage.config.bucket == "dummy_bucket"
    assert not _storage.status
    assert not _storage.user
    assert not _storage.usage
    _storage.delete()
