"""
Simvue User Alert
=================

Class for connecting with a local/remote user defined alert.

"""

import pydantic
import typing
from .base import AlertBase
from simvue.models import NAME_REGEX


class UserAlert(AlertBase):
    """Connect to/create a user defined alert either locally or on server"""

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        notification: typing.Literal["none", "email"],
        enabled: bool = True,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new user-defined alert

        Note all arguments are keyword arguments.

        Parameters
        ----------
        name : str
            the name to assign to this alert
        notification : "none" | "email"
            configure notification settings for this alert
        enabled : bool, optional
            whether this alert is enabled upon creation, default is True
        offline : bool, optional
            whether this alert should be created locally, default is False

        """
        _alert = UserAlert(
            name=name,
            notification=notification,
            source="user",
            enabled=enabled,
        )
        _alert.offline_mode(offline)
        return _alert
