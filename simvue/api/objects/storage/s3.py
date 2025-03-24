"""
Simvue S3 Storage
=================

Class for interacting with an S3 based storage on the server.

"""

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
    """Class for defining/accessing an S3 based storage system on the server."""

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        """Initialise an S3Storage instance attaching a configuration"""
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
        is_tenant_useable: bool,
        is_default: bool,
        is_enabled: bool,
        offline: bool = False,
        **__,
    ) -> Self:
        """Create a new S3 storage object.

        Parameters
        ----------
        name : str
            name to allocated to this storage system
        disable_check : bool
            whether to disable checks for this system
        endpoint_url : str
            endpoint defining the S3 upload URL
        region_name : str
            the region name associated with this storage system
        access_key_id : str
            the access key identifier for the storage
        secret_access_key : str
            the secret access key, stored as a secret string
        bucket : str
            the bucket associated with this storage system
        is_tenant_useable : bool
            whether this system is usable by the current tenant
        is_enabled : bool
            whether to enable this system
        is_default : bool
            if this storage system should become the new is_default
        offline : bool, optional
            if this instance should be created in offline mode, is_default False

        Returns
        -------
        S3Storage
            instance of storage system with staged changes

        """
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
            is_tenant_useable=is_tenant_useable,
            is_default=is_default,
            is_enabled=is_enabled,
            _read_only=False,
            _offline=offline,
        )
        _storage._staging |= _config
        return _storage

    @staging_check
    def get_config(self) -> dict[str, typing.Any]:
        """Retrieve configuration"""
        try:
            return self._get_attribute("config")
        except AttributeError:
            return {}


class Config:
    """S3 Configuration interface"""

    def __init__(self, storage: S3Storage) -> None:
        """Initialise a new configuration using an S3Storage object"""
        self._sv_obj = storage

    @property
    @staging_check
    def endpoint_url(self) -> str:
        """Set/retrieve the endpoint URL for this storage.

        Returns
        -------
        str
            the endpoint for this storage object
        """
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
        """Retrieve the region name for this storage"""
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
        """Modify the region name for this storage"""
        _config = self._sv_obj.get_config() | {"region_name": region_name}
        self._sv_obj._staging["config"] = _config

    @property
    @staging_check
    def bucket(self) -> str:
        """Retrieve the bucket label for this storage"""
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
        """Modify the bucket label for this storage"""
        if self._sv_obj.type == "file":
            raise ValueError(
                f"Cannot set attribute 'bucket' for storage type '{self._sv_obj.type}'"
            )

        _config = self._sv_obj.get_config() | {"bucket": bucket}
        self._sv_obj._staging["config"] = _config
