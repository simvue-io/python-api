"""
Simvue Server Folder
====================

Contains a class for remotely connecting to a Simvue folder, or defining
a new folder given relevant arguments.

"""

import pathlib
import typing
import datetime
import json

import pydantic

from simvue.exception import ObjectNotFoundError

from .base import SimvueObject, staging_check, write_only, Sort
from simvue.models import FOLDER_REGEX, DATETIME_FORMAT

# Need to use this inside of Generator typing to fix bug present in Python 3.10 - see issue #745
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


__all__ = ["Folder"]


T = typing.TypeVar("T", bound="Folder")


class FolderSort(Sort):
    @pydantic.field_validator("column")
    @classmethod
    def check_column(cls, column: str) -> str:
        if (
            column
            and column not in ("created", "modified", "path")
            and not column.startswith("metadata.")
        ):
            raise ValueError(f"Invalid sort column for folders '{column}")
        return column


class Folder(SimvueObject):
    """
    Simvue Folder
    =============

    This class is used to connect to/create folder objects on the Simvue server,
    any modification of instance attributes is mirrored on the remote object.

    """

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        """Initialise a Folder

        If an identifier is provided a connection will be made to the
        object matching the identifier on the target server.
        Else a new Folder will be created using arguments provided in kwargs.

        Parameters
        ----------
        identifier : str, optional
            the remote server unique id for the target folder
        read_only : bool, optional
            create object in read-only mode
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
        offline: bool = False,
        **kwargs,
    ) -> Self:
        """Create a new Folder on the Simvue server with the given path"""
        return Folder(path=path, _read_only=False, _offline=offline, **kwargs)

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.NonNegativeInt | None = None,
        sorting: list[FolderSort] | None = None,
        **kwargs,
    ) -> typing.Generator[tuple[str, T | None], None, None]:
        _params: dict[str, str] = kwargs

        if sorting:
            _params["sorting"] = json.dumps([i.to_params() for i in sorting])

        return super().get(count=count, offset=offset, **_params)

    @property
    @staging_check
    def tags(self) -> list[str]:
        """Return list of tags assigned to this folder"""
        return self._get_attribute("tags")

    @tags.setter
    @write_only
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        """Set tags assigned to this folder"""
        self._staging["tags"] = tags

    @property
    def path(self) -> pathlib.Path:
        """Return the path of this folder"""
        return self._get_attribute("path")

    @property
    @staging_check
    def description(self) -> str | None:
        """Return the folder description"""
        return self._get().get("description")

    @description.setter
    @write_only
    @pydantic.validate_call
    def description(self, description: str) -> None:
        """Update the folder description"""
        self._staging["description"] = description

    @property
    @staging_check
    def name(self) -> str | None:
        """Return the folder name"""
        return self._get().get("name")

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(self, name: str) -> None:
        """Update the folder name"""
        self._staging["name"] = name

    @property
    @staging_check
    def metadata(self) -> dict[str, int | str | None | float | dict] | None:
        """Return the folder metadata"""
        return self._get().get("metadata")

    @metadata.setter
    @write_only
    @pydantic.validate_call
    def metadata(self, metadata: dict[str, int | str | None | float | dict]) -> None:
        """Update the folder metadata"""
        self._staging["metadata"] = metadata

    @property
    @staging_check
    def star(self) -> bool:
        """Return if this folder is starred"""
        return self._get().get("starred", False)

    @star.setter
    @write_only
    @pydantic.validate_call
    def star(self, is_true: bool = True) -> None:
        """Star this folder as a favourite"""
        self._staging["starred"] = is_true

    @property
    @staging_check
    def ttl(self) -> int:
        """Return the retention period for this folder"""
        return self._get_attribute("ttl")

    @ttl.setter
    @write_only
    @pydantic.validate_call
    def ttl(self, time_seconds: int) -> None:
        """Update the retention period for this folder"""
        self._staging["ttl"] = time_seconds

    def delete(  # should params to this be optional and default to False?
        self,
        *,
        recursive: bool | None = False,
        delete_runs: bool | None = False,
        runs_only: bool | None = False,
    ) -> dict[str, typing.Any]:
        return super().delete(
            recursive=recursive, runs=delete_runs, runs_only=runs_only
        )

    @property
    def created(self) -> datetime.datetime | None:
        """Retrieve created datetime for the run"""
        _created: str | None = self._get_attribute("created")
        return (
            datetime.datetime.strptime(_created, DATETIME_FORMAT) if _created else None
        )


@pydantic.validate_call
def get_folder_from_path(
    path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
) -> Folder:
    _folders = Folder.get(filters=json.dumps([f"path == {path}"]), count=1)

    try:
        _, _folder = next(_folders)
    except StopIteration as e:
        raise ObjectNotFoundError(obj_type="folder", name=path) from e
    return _folder  # type: ignore
