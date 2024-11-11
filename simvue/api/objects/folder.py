"""
Simvue Server Folder
====================

Contains a class for remotely connecting to a Simvue folder, or defining
a new folder given relevant arguments.

"""

import pathlib
import typing

import pydantic
from .base import SimvueObject, Visibility
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
        **kwargs : dict
            any additional arguments to be passed to the object initialiser
        """
        self.visibility = Visibility(self)
        super().__init__(identifier, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls, *, path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)]
    ) -> typing.Self:
        """Create a new Folder on the Simvue server with the given path"""
        _folder = Folder()
        _folder._post(path=path)
        return _folder

    @property
    def tags(self) -> list[str]:
        """Return list of tags assigned to this folder"""
        try:
            return self._get()["tags"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'tags' for folder '{self._identifier}'"
            ) from e

    @tags.setter
    @pydantic.validate_call
    def tags(self, tags: list[str]) -> None:
        """Set tags assigned to this folder"""
        self._put(tags=tags)

    @property
    def path(self) -> pathlib.Path:
        """Return the path of this folder"""
        try:
            return self._get()["path"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'path' for folder '{self._identifier}'"
            ) from e

    @property
    def description(self) -> typing.Optional[str]:
        """Return the folder description"""
        return self._get().get("description")

    @description.setter
    @pydantic.validate_call
    def description(self, description: str) -> None:
        """Update the folder description"""
        self._put(description=description)

    @property
    def name(self) -> typing.Optional[str]:
        """Return the folder name"""
        return self._get().get("name")

    @name.setter
    @pydantic.validate_call
    def name(self, name: str) -> None:
        """Update the folder name"""
        self._put(name=name)

    @property
    def star(self) -> bool:
        """Return if this folder is starred"""
        return self._get().get("starred", False)

    @star.setter
    @pydantic.validate_call
    def star(self, is_true: bool = True) -> None:
        """Star this folder as a favourite"""
        self._put(starred=is_true)

    @property
    def ttl(self) -> int:
        """Return the retention period for this folder"""
        try:
            return self._get()["ttl"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'ttl' for folder '{self._identifier}'"
            ) from e

    @ttl.setter
    @pydantic.validate_call
    def ttl(self, time_seconds: int) -> None:
        """Update the retention period for this folder"""
        self._put(ttl=time_seconds)
