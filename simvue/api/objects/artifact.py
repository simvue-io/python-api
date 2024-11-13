import typing
import os.path
import pydantic

from simvue.models import NAME_REGEX
from simvue.utilities import get_mimetype_for_file, get_mimetypes, calculate_sha256
from .base import SimvueObject

Category = typing.Literal["code", "input", "output"]


class Artifact(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        run: str,
        storage: str | None,
        category: Category,
        file_path: pydantic.FilePath,
        file_type: str | None,
    ):
        _file_type = file_type or get_mimetype_for_file(file_path)

        if _file_type not in get_mimetypes():
            raise ValueError(f"Invalid MIME type '{file_type}' specified")

        _file_size = file_path.stat().st_size
        _file_orig_path = file_path.expanduser().absolute()
        _file_checksum = calculate_sha256(f"{file_path}", is_file=True)

        _artifact = Artifact()
        _artifact._post(
            name=name,
            run=run,
            storage=storage,
            category=category,
            originalPath=os.path.expandvars(_file_orig_path),
            size=_file_size,
            type=_file_type,
            checksum=_file_checksum,
        )

    @property
    def name(self) -> str:
        try:
            return self._get()["name"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'name' for artifact '{self._identifier}'"
            ) from e

    @property
    def checksum(self) -> str:
        try:
            return self._get()["checksum"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'checksum' for artifact '{self._identifier}'"
            ) from e

    @property
    def category(self) -> Category:
        try:
            return self._get()["category"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'category' for artifact '{self._identifier}'"
            ) from e

    @property
    def original_path(self) -> str:
        try:
            return self._get()["originalPath"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'originalPath' for artifact '{self._identifier}'"
            ) from e

    @property
    def storage(self) -> str:
        try:
            return self._get()["storage"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'storage' for artifact '{self._identifier}'"
            ) from e

    @property
    def type(self) -> str:
        try:
            return self._get()["type"]
        except KeyError as e:
            raise RuntimeError(
                f"Expected value for 'type' for artifact '{self._identifier}'"
            ) from e
