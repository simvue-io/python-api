"""Simvue user client for accessing API."""

from collections.abc import Generator
import json
from typing import Any

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

import pydantic

from simvue.api.objects.run import RunFilter, RunSort
from simvue.config.user import SimvueConfiguration
from simvue.api.objects import Run


def _server_url_factory() -> pydantic.AnyHttpUrl | None:
    _user_config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    return _user_config.server.url


def _server_token_factory() -> pydantic.SecretStr | None:
    _user_config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    return _user_config.server.token


class Client(pydantic.BaseModel):
    server_url: pydantic.AnyHttpUrl | None = pydantic.Field(
        default_factory=_server_url_factory
    )
    server_token: pydantic.SecretStr | None = pydantic.Field(
        default_factory=_server_token_factory
    )
    offline: bool = False
    _object_arguments: dict[str, Any] = pydantic.PrivateAttr(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def set_object_arguments(self) -> Self:
        """Set arguments attached to all object requests."""
        self._object_arguments |= {
            "mode": "offline" if self.offline else "online",
            "server_url": self.server_url,
            "server_token": self.server_token,
        }
        return self

    @pydantic.validate_call
    def get_runs(
        self,
        *,
        count_limit: pydantic.PositiveInt | None = None,
        start_index: pydantic.NonNegativeInt = 0,
        sort_by_columns: list[str] | None = None,
        ascending_order: bool = False,
        system: bool = False,
        metrics: bool = False,
        alerts: bool = False,
        timing: bool = False,
        aggregate: bool = False,
        filters: list[str] | None = None,
    ) -> Generator[tuple[str, Run]]:
        _sorting: list[RunSort] = [
            RunSort(column=column, descending=not ascending_order)
            for column in sort_by_columns or []
        ]
        if any((system, metrics, alerts, timing)):
            _params: dict[str, bool | str] = {
                "return_system": system,
                "return_alerts": alerts,
                "return_timing": timing,
                "return_metrics": metrics,
            }
        else:
            _params = {"return_basic": True}
        if filters:
            _params["filters"] = json.dumps(
                [str(f) for f in RunFilter.from_list(filters)]
            )
        _params["aggregate"] = aggregate

        for _, entry in Run.get(
            count=count_limit, sorting=_sorting, offset=start_index, **_params
        ):
            yield entry.to_dict()
