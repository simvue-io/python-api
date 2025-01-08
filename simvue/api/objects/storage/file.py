import typing

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import pydantic

from .base import StorageBase
from simvue.models import NAME_REGEX


class FileStorage(StorageBase):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        disable_check: bool,
        tenant_usable: bool,
        enabled: bool,
        default: bool,
        offline: bool = False,
    ) -> Self:
        """Create a new file storage object"""
        _storage = FileStorage(
            name=name,
            type="File",
            disable_check=disable_check,
            is_tenant_useable=tenant_usable,
            is_default=default,
            is_enabled=enabled,
            _read_only=False,
        )
        _storage.offline_mode(offline)
        return _storage
