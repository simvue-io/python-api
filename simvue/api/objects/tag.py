import pydantic.color
import typing
from .base import SimvueObject, staging_check

__all__ = ["Tag"]


class Tag(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: str,
        offline: bool = False,
    ):
        """Create a new Tag on the Simvue server"""
        _data: dict[str, typing.Any] = {"name": name}
        _tag = Tag(name=name)
        _tag.offline_mode(offline)
        return _tag

    @property
    @staging_check
    def name(self) -> str:
        return self._get_attribute("name")

    @name.setter
    @pydantic.validate_call
    def name(self, name: str) -> None:
        self._staging["name"] = name

    @property
    @staging_check
    def color(self) -> pydantic.color.RGBA:
        return pydantic.color.parse_str(self._get_attribute("colour"))

    @color.setter
    @pydantic.validate_call
    def color(self, color: pydantic.color.Color) -> None:
        self._staging["colour"] = color.as_hex()

    @property
    @staging_check
    def description(self) -> str:
        return self._get_attribute("description")

    @description.setter
    @pydantic.validate_call
    def description(self, description: str) -> None:
        self._staging["description"] = description
