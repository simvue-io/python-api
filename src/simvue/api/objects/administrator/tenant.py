"""
Simvue Tenants
==============

Contains a class for remotely connecting to Simvue tenants, or defining
a new tenant given relevant arguments.

"""

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import pydantic

from simvue.api.objects.base import write_only, SimvueObject, staging_check


class Tenant(SimvueObject):
    """Class for interacting with a tenant instance on the server."""

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: str,
        is_enabled: bool = True,
        max_request_rate: int = 0,
        max_runs: int = 0,
        max_data_volume: int = 0,
        offline: bool = False,
    ) -> Self:
        """Create a new tenant on the Simvue server.

        Requires administrator privileges.

        Parameters
        ----------
        name: str
            the name for this tenant
        is_enabled: bool, optional
            whether to enable the tenant on creation, default is True
        max_request_rate: int, optional
            the maximum request rate allowed for this tenant, default is no limit.
        max_runs: int, optional
            the maximum number of runs allowed within this tenant, default is no limit.
        max_data_volume: int, optional
            the maximum volume of data allowed within this tenant, default is no limit.
        offline: bool, optional
            create in offline mode, default is False.

        Returns
        -------
        Tenant
            a tenant instance with staged changes

        """
        return Tenant(
            name=name,
            is_enabled=is_enabled,
            max_request_rate=max_request_rate,
            max_runs=max_runs,
            max_data_volume=max_data_volume,
            _read_only=False,
            _offline=offline,
        )

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
    def is_enabled(self) -> bool:
        """Retrieve if tenant is enabled"""
        return self._get_attribute("is_enabled")

    @is_enabled.setter
    @write_only
    @pydantic.validate_call
    def is_enabled(self, is_enabled: bool) -> None:
        """Enable/disable tenant"""
        self._staging["is_enabled"] = is_enabled

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
