import pydantic
import typing
from .base import AlertBase
from simvue.models import NAME_REGEX


class UserAlert(AlertBase):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        notification: typing.Literal["none", "email"],
        enabled: bool = True,
        tags: list[str] | None = None,
        offline: bool = False,
    ) -> typing.Self:
        _alert = UserAlert(
            name=name,
            notification=notification,
            source="user",
            enabled=enabled,
            tags=tags or [],
        )
        _alert.offline_mode(offline)
        return _alert
