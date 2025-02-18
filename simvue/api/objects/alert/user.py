"""
Simvue User Alert
=================

Class for connecting with a local/remote user defined alert.

"""

import pydantic
import typing

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import http

from simvue.api.request import get_json_from_response, put as sv_put
from .base import AlertBase
from simvue.models import NAME_REGEX


class UserAlert(AlertBase):
    """Connect to/create a user defined alert either locally or on server"""

    def __init__(self, identifier: str | None = None, **kwargs) -> None:
        super().__init__(identifier, **kwargs)
        self._local_status: dict[str, str | None] = kwargs.pop("status", {})

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        description: str | None,
        notification: typing.Literal["none", "email"],
        enabled: bool = True,
        offline: bool = False,
        **_,
    ) -> Self:
        """Create a new user-defined alert

        Note all arguments are keyword arguments.

        Parameters
        ----------
        name : str
            the name to assign to this alert
        description : str | None
            description for this alert
        notification : "none" | "email"
            configure notification settings for this alert
        enabled : bool, optional
            whether this alert is enabled upon creation, default is True
        offline : bool, optional
            whether this alert should be created locally, default is False

        """
        _alert = UserAlert(
            name=name,
            description=description,
            notification=notification,
            source="user",
            enabled=enabled,
            _read_only=False,
            _offline=offline,
        )
        _alert._params = {"deduplicate": True}
        return _alert

    @classmethod
    def get(
        cls, count: int | None = None, offset: int | None = None
    ) -> dict[str, typing.Any]:
        """Return only UserAlerts"""
        raise NotImplementedError("Retrieve of only user alerts is not yet supported")

    def get_status(self, run_id: str) -> typing.Literal["ok", "critical"] | None:
        """Retrieve current alert status for the given run"""
        if self._offline:
            return self._staging.get("status", self._local_status).get(run_id)

        return super().get_status(run_id)

    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        """Set status update on reconnect"""
        for offline_id, status in self._staging.get("status", {}).items():
            self.set_status(id_mapping.get(offline_id), status)

    @pydantic.validate_call
    def set_status(self, run_id: str, status: typing.Literal["ok", "critical"]) -> None:
        """Set the status of this alert for a given run"""
        if self._offline:
            if "status" not in self._staging:
                self._staging["status"] = {}
            self._staging["status"][run_id] = status
            return

        _response = sv_put(
            url=self.url / "status" / run_id,
            data={"status": status},
            headers=self._headers,
        )

        get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Updating state of alert '{self._identifier}' to '{status}'",
        )
