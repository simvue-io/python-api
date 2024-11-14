import typing
import pydantic

from .base import Storage, staging_check
from simvue.models import NAME_REGEX


class S3Storage(Storage):
    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        self.config = Config(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        disable_check: bool,
        endpoint_url: str,
        region_name: str,
        access_key_id: str,
        secret_access_key: pydantic.SecretStr,
        bucket: str,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new S3 storage object"""
        _config: dict[str, str] = {
            "endpoint_url": endpoint_url,
            "region_name": region_name,
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key.get_secret_value(),
            "bucket": bucket,
        }
        _storage = S3Storage(
            name=name, type="S3", config=_config, disable_check=disable_check
        )
        _storage.offline_mode(offline)
        return _storage

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
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Storage type '{self._sv_obj.type}' has no attribute 'endpoint_url'"
            )

        try:
            return self._sv_obj.get_config()["endpoint_url"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @endpoint_url.setter
    def endpoint_url(self, endpoint_url: str) -> None:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Cannot set attribute 'endpoint_url' for storage type '{self._sv_obj.type}'"
            )

        _config = self._sv_obj.get_config() | {"endpoint_url": endpoint_url}
        self._sv_obj._staging["config"] = _config

    @property
    @staging_check
    def region_name(self) -> str:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Storage type '{self._sv_obj.type}' has no attribute 'region_name'"
            )

        try:
            return self._sv_obj.get_config()["region_name"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @region_name.setter
    def region_name(self, region_name: str) -> None:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Cannot set attribute 'region_name' for storage type '{self._sv_obj.type}'"
            )

        _config = self._sv_obj.get_config() | {"region_name": region_name}
        self._sv_obj._staging["config"] = _config

    @property
    @staging_check
    def access_key_id(self) -> str:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Storage type '{self._sv_obj.type}' has no attribute 'access_key_id'"
            )

        try:
            return self._sv_obj.get_config()["access_key_id"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @access_key_id.setter
    def access_key_id(self, access_key_id: str) -> None:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Cannot set attribute 'access_key_id' for storage type '{self._sv_obj.type}'"
            )

        _config = self._sv_obj.get_config() | {"access_key_id": access_key_id}
        self._sv_obj._staging["config"] = _config

    @property
    @staging_check
    def secret_access_key(self) -> pydantic.SecretStr:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Storage type '{self._sv_obj.type}' has no attribute 'secret_access_key'"
            )

        try:
            return pydantic.SecretStr(self._sv_obj.get_config()["secret_access_key"])
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @secret_access_key.setter
    def secret_access_key(self, secret_access_key: pydantic.SecretStr) -> None:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Cannot set attribute 'secret_access_key' for storage type '{self._sv_obj.type}'"
            )

        _config = self._sv_obj.get_config() | {
            "secret_access_key": secret_access_key.get_secret_value()
        }
        self._sv_obj._staging["config"] = _config

    @property
    @staging_check
    def bucket(self) -> str:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Storage type '{self._sv_obj.type}' has no attribute 'bucket'"
            )

        try:
            return self._sv_obj.get_config()["bucket"]
        except KeyError as e:
            raise RuntimeError(
                "Expected key 'frequency' in alert definition retrieval"
            ) from e

    @bucket.setter
    def bucket(self, bucket: str) -> None:
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Cannot set attribute 'bucket' for storage type '{self._sv_obj.type}'"
            )

        _config = self._sv_obj.get_config() | {"bucket": bucket}
        self._sv_obj._staging["config"] = _config
