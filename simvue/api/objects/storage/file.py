"""
Simvue File Storage
===================

Class for interacting with a file based storage on the server.

"""

import typing

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import pydantic

from .base import StorageBase
from simvue.models import NAME_REGEX


class FileStorage(StorageBase):
    """
    Simvue File Storage
    ===================

    This class is used to connect to/create file storage objects on the Simvue server,
    any modification of instance attributes is mirrored on the remote object.

    """

    def __init__(
        self,
        identifier: str | None = None,
        _read_only: bool = False,
        **kwargs,
    ) -> None:
        """Initialise a File Storage

        If an identifier is provided a connection will be made to the
        object matching the identifier on the target server.
        Else a new FileStorage instance will be created using arguments provided in kwargs.

        Parameters
        ----------
        identifier : str, optional
            the remote server unique id for the target folder
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        disable_check: bool,
        is_tenant_useable: bool,
        is_enabled: bool,
        is_default: bool,
        offline: bool = False,
        **_,
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
        return FileStorage(
            name=name,
            backend="File",
            disable_check=disable_check,
            is_tenant_useable=is_tenant_useable,
            is_default=is_default,
            is_enabled=is_enabled,
            _read_only=False,
            _offline=offline,
        )
