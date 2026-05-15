"""Simvue Server Tag.

Contains a class for remotely connecting to a Simvue Tag, or defining
a new tag given relevant arguments.

"""

import typing
import json
import datetime
import pydantic
import pydantic_extra_types.color as pyd_color

from simvue.api.objects.base import SimvueObject, Sort, staging_check, write_only
from simvue.models import DATETIME_FORMAT
from collections.abc import Generator

try:
    from typing import Self, override
except ImportError:
    from typing_extensions import Self, override

__all__ = ["Tag"]


class TagSort(Sort):
    @pydantic.field_validator("column")
    @classmethod
    def check_column(cls, column: str) -> str:
        if column and column not in ("created", "name"):
            raise ValueError(f"Invalid sort column for tags '{column}")
        return column


class Tag(SimvueObject):
    """Simvue Tag.

    This class is used to connect to/create tag objects on the Simvue server,
    any modification of instance attributes is mirrored on the remote object.

    """

    @override
    def __init__(
        self,
        identifier: str | None = None,
        server_url: str | None = None,
        server_token: pydantic.SecretStr | None = None,
        **kwargs,
    ) -> None:
        """Initialise a Tag

        If an identifier is provided a connection will be made to the
        object matching the identifier on the target server.
        Else a new Tag will be created using arguments provided in kwargs.

        Parameters
        ----------
        identifier : str, optional
            the remote server unique id for the target folder
        server_url: str | None, optional
            alternative server URL, default None
        server_token : str | None, optional
            token for alternative server, default None
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        super().__init__(
            identifier, server_url=server_url, server_token=server_token, **kwargs
        )

    @override
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: str,
        offline: bool = False,
        server_url: str | None = None,
        server_token: pydantic.SecretStr | None = None,
        **kwargs,
    ) -> Self:
        """Create a new Tag on the Simvue server.

        Parameters
        ----------
        name : str
            name for the tag
        offline : bool, optional
            create this tag in offline mode, default False.
        server_url: str | None, optional
            alternative server URL, default None
        server_token : str | None, optional
            token for alternative server, default None

        Returns
        -------
        Tag
            tag object with staged attributes
        """
        _data: dict[str, typing.Any] = {"name": name}
        return cls(
            name=name,
            server_url=server_url,
            server_token=server_token,
            _offline=offline,
            _read_only=False,
            **kwargs,
        )

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
    def colour(self) -> pyd_color.RGBA:
        """Retrieve the tag colour"""
        return pyd_color.parse_str(self._get_attribute("colour"))

    @colour.setter
    @write_only
    @pydantic.validate_call
    def colour(self, colour: pyd_color.Color) -> None:
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
            datetime.datetime.strptime(_created, DATETIME_FORMAT).replace(
                tzinfo=datetime.timezone.utc
            )
            if _created
            else None
        )

    @override
    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        *,
        count: int | None = None,
        offset: int | None = None,
        sorting: list[TagSort] | None = None,
        server_url: str | None = None,
        server_token: pydantic.SecretStr | None = None,
        **kwargs,
    ) -> Generator[tuple[str, "SimvueObject"]]:
        """Get tags from the server.

        Parameters
        ----------
        count : int, optional
            limit the number of objects returned, default no limit.
        offset : int, optional
            start index for results, default is 0.
        sorting : list[dict] | None, optional
            list of sorting definitions in the form {'column': str, 'descending': bool}
        server_url: str | None, optional
            alternative server URL, default None
        server_token : str | None, optional
            token for alternative server, default None

        Yields
        ------
        tuple[str, Tag]
            id of tag
            Tag object representing object on server
        """
        # There are currently no tag filters
        _ = kwargs.pop("filters", None)

        _params: dict[str, str] = {}

        if sorting:
            _params["sorting"] = json.dumps([i.to_params() for i in sorting])

        return super().get(
            count=count,
            offset=offset,
            server_url=server_url,
            server_token=server_token,
            **_params,
            **kwargs,
        )
