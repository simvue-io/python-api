try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import pydantic

from simvue.api.objects.base import write_only, SimvueObject, staging_check


class Tenant(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: str,
        enabled: bool = True,
        max_request_rate: int = 0,
        max_runs: int = 0,
        max_data_volume: int = 0,
        offline: bool = False,
    ) -> Self:
        _tenant = Tenant(
            name=name,
            enabled=enabled,
            max_request_rate=max_request_rate,
            max_runs=max_runs,
            max_data_volume=max_data_volume,
            offline=offline,
            _read_only=False,
        )
        _tenant.offline_mode(offline)
        return _tenant  # type: ignore

    @property
    def name(self) -> str:
        """Retrieve the name of the tenant"""
        return self._get_attribute("name")

    @name.setter
    @write_only
    @pydantic.validate_call
    def name(self, name: str) -> None:
        """Change name of tenant"""
        self._staging["name"] = name

    @property
    @staging_check
    def enabled(self) -> bool:
        """Retrieve if tenant is enabled"""
        return self._get_attribute("is_enabled")

    @enabled.setter
    @write_only
    @pydantic.validate_call
    def enabled(self, enabled: bool) -> None:
        """Enable/disable tenant"""
        self._staging["is_enabled"] = enabled

    @property
    @staging_check
    def max_request_rate(self) -> int:
        """Retrieve the tenant's maximum request rate"""
        return self._get_attribute("max_request_rate")

    @max_request_rate.setter
    @write_only
    @pydantic.validate_call
    def max_request_rate(self, max_request_rate: int) -> None:
        """Update tenant's maximum request rate"""
        self._staging["max_request_rate"] = max_request_rate

    @property
    @staging_check
    def max_runs(self) -> int:
        """Retrieve the tenant's maximum runs"""
        return self._get_attribute("max_runs")

    @max_runs.setter
    @write_only
    @pydantic.validate_call
    def max_runs(self, max_runs: int) -> None:
        """Update tenant's maximum runs"""
        self._staging["max_runs"] = max_runs

    @property
    @staging_check
    def max_data_volume(self) -> int:
        """Retrieve the tenant's maximum data volume"""
        return self._get_attribute("max_data_volume")

    @max_data_volume.setter
    @write_only
    @pydantic.validate_call
    def max_data_volume(self, max_data_volume: int) -> None:
        """Update tenant's maximum data volume"""
        self._staging["max_data_volume"] = max_data_volume
