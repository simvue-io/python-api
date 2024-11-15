import typing
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
        default: bool,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new file storage object"""
        _storage = FileStorage(
            name=name,
            type="File",
            disable_check=disable_check,
            tenant_useable=tenant_usable,
            default=default,
        )
        _storage.offline_mode(offline)
        return _storage
