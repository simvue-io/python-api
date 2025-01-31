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
    """Class for creation/interaction with tag object on server"""

    @classmethod
    @pydantic.validate_call
    def new(cls, *, name: str, offline: bool = False, **kwargs):
        """Create a new Tag on the Simvue server.

        Parameters
        ----------
        name : str
            name for the tag
        offline : bool, optional
            create this tag in offline mode, default False.

        Returns
        -------
        Tag
            tag object with staged attributes
        """
        _data: dict[str, typing.Any] = {"name": name}
        return Tag(name=name, _read_only=False, _offline=offline, **kwargs)

    @property
    @staging_check
    def name(self) -> str:
        """Retrieve the tag name"""
        return self._get_attribute("name")

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(self, name: str) -> None:
        """Set the tag name"""
        self._staging["name"] = name

    @property
    @staging_check
    def colour(self) -> pydantic.color.RGBA:
        """Retrieve the tag colour"""
        return pydantic.color.parse_str(self._get_attribute("colour"))

    @colour.setter
    @write_only
    @pydantic.validate_call
    def colour(self, colour: pydantic.color.Color) -> None:
        """Set the tag colour"""
        self._staging["colour"] = colour.as_hex()

    @property
    @staging_check
    def description(self) -> str:
        """Get description for this tag"""
        return self._get_attribute("description")

    @description.setter
    @write_only
    @pydantic.validate_call
    def description(self, description: str) -> None:
        """Set the description for this tag"""
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
        """Get tags from the server.

        Parameters
        ----------
        count : int, optional
            limit the number of objects returned, default no limit.
        offset : int, optional
            start index for results, default is 0.

        Yields
        ------
        tuple[str, Tag]
            id of tag
            Tag object representing object on server
        """
        # There are currently no tag filters
        kwargs.pop("filters", None)

        return super().get(count=count, offset=offset, **kwargs)
