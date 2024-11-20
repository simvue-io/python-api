"""
Simvue Server Folder
====================

Contains a class for remotely connecting to a Simvue folder, or defining
a new folder given relevant arguments.

"""

import pathlib
import typing

import pydantic

from .base import SimvueObject, Visibility, staging_check, write_only
from simvue.models import FOLDER_REGEX


class Folder(SimvueObject):
    """
    Simvue Folder
    =============

    This class is used to connect to/create folder objects on the Simvue server,
    any modification of instance attributes is mirrored on the remote object.

    """

    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
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
        self.visibility = Visibility(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
        offline: bool = False,
    ):
        """Create a new Folder on the Simvue server with the given path"""
        _folder = Folder(path=path, _read_only=False)
        _folder.offline_mode(offline)
        return _folder

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
    def description(self) -> typing.Optional[str]:
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
    def name(self) -> typing.Optional[str]:
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

    def delete(self, *, recursive: bool, delete_runs: bool) -> dict[str, typing.Any]:
        return super().delete(recursive=recursive, runs=delete_runs)
