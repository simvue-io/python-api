import typing
import pydantic

from .base import Storage
from simvue.models import NAME_REGEX


class FileStorage(Storage):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        disable_check: bool,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new file storage object"""
        _storage = FileStorage(name=name, type="file", disable_check=disable_check)
        _storage.offline_mode(offline)
        return _storage
