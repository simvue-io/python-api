"""Simvue Storage Base.

Contains general definitions for Simvue Storage objects.
"""

import datetime
import typing

import pydantic

from simvue.api.objects.base import SimvueObject, staging_check, write_only
from simvue.models import DATETIME_FORMAT, NAME_REGEX

try:
    from typing import Self
except ImportError:
    from typing import Self

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035


class StorageBase(SimvueObject):
    """Storage object base class from which all storage types inherit.

    This represents a single storage backend used to store uploaded artifacts.

    """

    def __init__(
        self,
        obj_type: str,
        identifier: str | None = None,
        *,
        _read_only: bool = False,
        _offline: bool = False,
        _user_agent: str | None = None,
        _local: bool = False,
        **kwargs: object,
    ) -> None:
        """Retrieve an alert from the Simvue server by identifier."""
        self._label: str = "storage"
        self._endpoint: str = self._label
        self.type: str = obj_type
        super().__init__(
            identifier,
            _read_only=_read_only,
            _offline=_offline,
            _user_agent=_user_agent,
            _local=_local,
            **kwargs,
        )

    @classmethod
    @override
    def new(cls, **_: typing.Any) -> Self:
        """Create a new instance of a storage type."""
        raise NotImplementedError

    @property
    @staging_check
    def name(self) -> str:
        """Retrieve the name for this storage."""
        _name: str = typing.cast("str", self._get_attribute("name"))
        return _name

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> None:
        """Set name assigned to this folder."""
        self._staging["name"] = name

    @property
    def backend(self) -> str:
        """Retrieve the backend of storage."""
        _backend: str = typing.cast("str", self._get_attribute("backend"))
        return _backend

    @property
    @staging_check
    def is_default(self) -> bool:
        """Retrieve if this is the default storage for the user."""
        _is_default: bool = typing.cast("bool", self._get_attribute("is_default"))
        return _is_default

    @is_default.setter
    @write_only
    @pydantic.validate_call
    def is_default(self, is_default: bool) -> None:
        """Set this storage to be the default."""
        self._staging["is_default"] = is_default

    @property
    @staging_check
    def is_tenant_useable(self) -> bool:
        """Retrieve if this is usable by the current user tenant."""
        _is_tenant_useable: bool = typing.cast(
            "bool", self._get_attribute("is_tenant_useable")
        )
        return _is_tenant_useable

    @is_tenant_useable.setter
    @write_only
    @pydantic.validate_call
    def is_tenant_useable(self, is_tenant_useable: bool) -> None:
        """Set this storage to be usable by the current user tenant."""
        self._staging["is_tenant_useable"] = is_tenant_useable

    @property
    @staging_check
    def is_enabled(self) -> bool:
        """Retrieve if this is enabled."""
        _is_enabled: bool = typing.cast("bool", self._get_attribute("is_enabled"))
        return _is_enabled

    @is_enabled.setter
    @write_only
    @pydantic.validate_call
    def is_enabled(self, is_enabled: bool) -> None:
        """Set this storage to be usable by the current user tenant."""
        self._staging["is_enabled"] = is_enabled

    @property
    def created(self) -> datetime.datetime | None:
        """Retrieve created datetime for the artifact."""
        _created: str | None = typing.cast("str | None", self._get_attribute("created"))
        return (
            datetime.datetime.strptime(_created, DATETIME_FORMAT).astimezone(
                datetime.UTC
            )
            if _created
            else None
        )
