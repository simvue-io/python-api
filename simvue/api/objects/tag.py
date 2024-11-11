import pydantic.color
import typing
from .base import SimvueObject


class Tag(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: str,
        description: str | None = None,
        color: pydantic.color.Color | None = None,
    ) -> typing.Self:
        """Create a new Tag on the Simvue server"""
        _data: dict[str, typing.Any] = {"name": name}
        if description:
            _data["description"] = description
        if color:
            _data["description"] = color.as_hex()
        _tag = Tag()
        _tag._post(**_data)
        return _tag

    @property
    def name(self) -> str:
        try:
            return self._get()["name"]
        except KeyError as e:
            raise RuntimeError("Expected key 'name' in tag retrieval") from e

    @name.setter
    @pydantic.validate_call
    def name(self, name: str) -> None:
        self._put(name=name)

    @property
    def color(self) -> pydantic.color.RGBA:
        try:
            _color: str = self._get()["colour"]
            return pydantic.color.parse_str(_color)
        except KeyError as e:
            raise RuntimeError("Expected key 'colour' in tag retrieval") from e

    @color.setter
    @pydantic.validate_call
    def color(self, color: pydantic.color.Color) -> None:
        self._put(colour=color.as_hex())

    @property
    def description(self) -> str:
        try:
            return self._get()["description"]
        except KeyError as e:
            raise RuntimeError("Expected key 'description' in tag retrieval") from e

    @description.setter
    @pydantic.validate_call
    def description(self, description: str) -> None:
        self._put(description=description)
