import pytest
import time
import json
import uuid

from simvue.api.objects import S3Storage

@pytest.mark.api
def test_create_s3_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _storage = S3Storage.new(
        name=_uuid,
        endpoint_url="https://not_a_real_url.io",
        disable_check=False,
        region_name="fictionsville",
        access_key_id="dummy_key",
        secret_access_key="not_a_key",
        bucket="dummy_bucket"
    )
    _storage.commit()
    assert _storage.name == _uuid
    assert not _storage.disable_check
    assert _storage.config.endpoint_url == "https://not_a_real_url.io"
    assert _storage.config.region_name == "fictionsville"
    assert _storage.config.access_key_id == "dummy_key"
    assert _storage.config.secret_access_key.get_secret_value() == "not_a_key"
    assert _storage.config.bucket == "dummy_bucket"
    _storage.delete()


@pytest.mark.api
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
        offline=True
    )
    _storage.commit()
    assert _storage.name == _uuid
    assert not _storage.disable_check
    assert _storage.config.endpoint_url == "https://not_a_real_url.io"
    assert _storage.config.region_name == "fictionsville"
    assert _storage.config.access_key_id == "dummy_key"
    assert _storage.config.secret_access_key.get_secret_value() == "not_a_key"
    assert _storage.config.bucket == "dummy_bucket"
    _storage.delete()
