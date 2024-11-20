import typing

import pydantic
from simvue.api.objects.base import SimvueObject, staging_check, write_only
from simvue.models import NAME_REGEX


class StorageBase(SimvueObject):
    def __init__(
        self, identifier: typing.Optional[str] = None, read_only: bool = False, **kwargs
    ) -> None:
        """Retrieve an alert from the Simvue server by identifier"""
        self._label = "storage"
        self._endpoint = self._label
        super().__init__(identifier, read_only, **kwargs)
        self.status = Status(self)

    @classmethod
    def new(cls, **kwargs):
        pass

    def get_status(self) -> dict[str, typing.Any]:
        return {} if self._offline else self._get_attribute("status")

    @property
    @staging_check
    def name(self) -> str:
        """Retrieve the name for this storage"""
        return self._get_attribute("name")

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> None:
        """Set name assigned to this folder"""
        self._staging["name"] = name

    @property
    def type(self) -> str:
        """Retrieve the type of storage"""
        return self._get_attribute("type")

    @property
    @staging_check
    def default(self) -> bool:
        """Retrieve if this is the default storage for the user"""
        return self._get_attribute("default")

    @default.setter
    @write_only
    @pydantic.validate_call
    def default(self, is_default: bool) -> None:
        """Set this storage to be the default"""
        self._staging["default"] = is_default

    @property
    @staging_check
    def tenant_usable(self) -> bool:
        """Retrieve if this is usable by the current user tenant"""
        return self._get_attribute("tenant_usable")

    @tenant_usable.setter
    @write_only
    @pydantic.validate_call
    def tenant_usable(self, is_tenant_usable: bool) -> None:
        """Set this storage to be usable by the current user tenant"""
        self._staging["tenant_usable"] = is_tenant_usable

    @property
    def usage(self) -> int | None:
        return None if self._offline else self._get_attribute("usage")

    @property
    def user(self) -> str | None:
        return None if self._offline else self._get_attribute("user")


class Status:
    def __init__(self, storage: StorageBase) -> None:
        self._sv_obj = storage

    @property
    def status(self) -> str:
        try:
            return self._sv_obj.get_status()["status"]
        except KeyError as e:
            raise RuntimeError("Expected key 'status' in status retrieval") from e

    @property
    def timestamp(self) -> str:
        try:
            return self._sv_obj.get_status()["timestamp"]
        except KeyError as e:
            raise RuntimeError("Expected key 'timestamp' in status retrieval") from e
