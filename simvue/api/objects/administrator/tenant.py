import typing

import pydantic
from .base import SimvueObject, staging_check


class Tenant(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(
        cls, *, name: str, enabled: bool = True, offline: bool = False
    ) -> typing.Self:
        _tenant = Tenant(name=name, enabled=enabled, offline=offline)
        _tenant.offline_mode(offline)
        return _tenant  # type: ignore

    @property
    def name(self) -> str:
        """Retrieve the name of the tenant"""
        return self._get_attribute("name")

    @property
    @staging_check
    def enabled(self) -> bool:
        """Retrieve if alert is enabled"""
        return self._get_attribute("enabled")

    @enabled.setter
    @pydantic.validate_call
    def enabled(self, enabled: str) -> None:
        """Enable/disable alert"""
        self._staging["enabled"] = enabled
