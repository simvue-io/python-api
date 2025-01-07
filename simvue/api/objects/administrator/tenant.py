try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import pydantic

from simvue.api.objects.base import write_only, SimvueObject, staging_check


class Tenant(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(cls, *, name: str, enabled: bool = True, offline: bool = False) -> Self:
        _tenant = Tenant(name=name, enabled=enabled, offline=offline, _read_only=False)
        _tenant.offline_mode(offline)
        return _tenant  # type: ignore

    @property
    def name(self) -> str:
        """Retrieve the name of the tenant"""
        return self._get_attribute("name")

    @property
    @staging_check
    def enabled(self) -> bool:
        """Retrieve if tenant is enabled"""
        return self._get_attribute("enabled")

    @enabled.setter
    @write_only
    @pydantic.validate_call
    def enabled(self, enabled: str) -> None:
        """Enable/disable tenant"""
        self._staging["enabled"] = enabled
