import typing

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import pydantic

from simvue.api.objects.base import write_only

from .base import StorageBase, staging_check
from simvue.models import NAME_REGEX


class S3Storage(StorageBase):
    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        self.config = Config(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        disable_check: bool,
        endpoint_url: pydantic.HttpUrl,
        region_name: str,
        access_key_id: str,
        secret_access_key: pydantic.SecretStr,
        bucket: str,
        tenant_useable: bool,
        default: bool,
        offline: bool = False,
        **__,
    ) -> Self:
        """Create a new S3 storage object"""
        _config: dict[str, str] = {
            "endpoint_url": endpoint_url.__str__(),
            "region_name": region_name,
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key.get_secret_value(),
            "bucket": bucket,
        }
        _storage = S3Storage(
            name=name,
            backend="S3",
            config=_config,
            disable_check=disable_check,
            tenant_useable=tenant_useable,
            default=default,
            _read_only=False,
        )
        _storage._staging |= _config
        _storage.offline_mode(offline)
        return _storage

    @staging_check
    def get_config(self) -> dict[str, typing.Any]:
        """Retrieve configuration"""
        try:
            return self._get_attribute("config")
        except AttributeError:
            return {}


class Config:
    def __init__(self, storage: S3Storage) -> None:
        self._sv_obj = storage

    @property
    @staging_check
    def endpoint_url(self) -> str:
        try:
            return self._sv_obj.get_config()["endpoint_url"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'endpoint_url' in alert definition retrieval"
            ) from e

    @endpoint_url.setter
    @write_only
    @pydantic.validate_call
    def endpoint_url(self, endpoint_url: pydantic.HttpUrl) -> None:
        _config = self._sv_obj.get_config() | {"endpoint_url": endpoint_url.__str__()}
        self._sv_obj._staging["config"] = _config

    @property
    @staging_check
    def region_name(self) -> str:
        try:
            return self._sv_obj.get_config()["region_name"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'region_name' in alert definition retrieval"
            ) from e

    @region_name.setter
    @write_only
    @pydantic.validate_call
    def region_name(self, region_name: str) -> None:
        _config = self._sv_obj.get_config() | {"region_name": region_name}
        self._sv_obj._staging["config"] = _config

    @property
    @staging_check
    def bucket(self) -> str:
        try:
            return self._sv_obj.get_config()["bucket"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'bucket' in alert definition retrieval"
            ) from e

    @bucket.setter
    @write_only
    @pydantic.validate_call
    def bucket(self, bucket: str) -> None:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Cannot set attribute 'bucket' for storage type '{self._sv_obj.type}'"
            )

        _config = self._sv_obj.get_config() | {"bucket": bucket}
        self._sv_obj._staging["config"] = _config
