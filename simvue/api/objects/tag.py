"""
Simvue Server Tag
=================

Contains a class for remotely connecting to a Simvue Tag, or defining
a new tag given relevant arguments.

"""

import pydantic.color
import typing
import datetime
from .base import SimvueObject, staging_check, write_only
from simvue.models import DATETIME_FORMAT

__all__ = ["Tag"]


class Tag(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(cls, *, name: str, offline: bool = False, **kwargs):
        """Create a new Tag on the Simvue server"""
        _data: dict[str, typing.Any] = {"name": name}
        _tag = Tag(name=name, _read_only=False, **kwargs)
        _tag.offline_mode(offline)
        return _tag

    @property
    @staging_check
    def name(self) -> str:
        return self._get_attribute("name")

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(self, name: str) -> None:
        self._staging["name"] = name

    @property
    @staging_check
    def color(self) -> pydantic.color.RGBA:
        return pydantic.color.parse_str(self._get_attribute("colour"))

    @color.setter
    @write_only
    @pydantic.validate_call
    def color(self, color: pydantic.color.Color) -> None:
        self._staging["colour"] = color.as_hex()

    @property
    @staging_check
    def description(self) -> str:
        return self._get_attribute("description")

    @description.setter
    @write_only
    @pydantic.validate_call
    def description(self, description: str) -> None:
        self._staging["description"] = description

    @property
    def created(self) -> datetime.datetime | None:
        """Retrieve created datetime for the run"""
        _created: str | None = self._get_attribute("created")
        return (
            datetime.datetime.strptime(_created, DATETIME_FORMAT) if _created else None
        )

    @classmethod
    def get(
        cls, *, count: int | None = None, offset: int | None = None, **kwargs
    ) -> typing.Generator[tuple[str, "SimvueObject"], None, None]:
        # There are currently no tag filters
        kwargs.pop("filters", None)

        return super().get(count=count, offset=offset, **kwargs)
