"""Simvue File Storage.

Class for interacting with a file based storage on the server.

"""

import typing

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035

import pydantic

from simvue.models import NAME_REGEX

from .base import StorageBase

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035


class FileStorage(StorageBase):
    """Class for defining/accessing a File based storage system on the server."""

    @classmethod
    @pydantic.validate_call
    @override
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        disable_check: bool,
        is_tenant_useable: bool,
        is_enabled: bool,
        is_default: bool,
        offline: bool = False,
        **_: object,
    ) -> Self:
        """Create a new file storage object.

        Parameters
        ----------
        name : str
            name to allocated to this storage system
        disable_check : bool
            whether to disable checks for this system
        is_tenant_useable : bool
            whether this system is usable by the current tenant
        is_enabled : bool
            whether to enable this system
        is_default : bool
            if this storage system should become the new default
        offline : bool, optional
            if this instance should be created in offline mode, default False

        Returns
        -------
        FileStorage
            instance of storage system with staged changes
        """
        return cls(
            name=name,
            backend="File",
            disable_check=disable_check,
            is_tenant_useable=is_tenant_useable,
            is_default=is_default,
            is_enabled=is_enabled,
            _read_only=False,
            _offline=offline,
        )
