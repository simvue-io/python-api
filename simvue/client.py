"""Simvue client for server data retrieval."""

from collections.abc import Generator
import json
import typing
import pydantic

from simvue.api.objects.filter import FoldersFilter
from simvue.config.user import SimvueConfiguration
from simvue.api.objects import Folder, Run

if typing.TYPE_CHECKING:
    from simvue.api.objects.filter import RunsFilter
    from pandas import DataFrame


def _server_url_factory() -> pydantic.AnyHttpUrl:
    _config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    return _config.server.url


def _server_token_factory() -> pydantic.SecretStr:
    _config: SimvueConfiguration = SimvueConfiguration.fetch(mode="offline")
    return _config.server.token


class Client(pydantic.BaseModel):
    server_url: pydantic.AnyHttpUrl = pydantic.Field(
        default_factory=_server_url_factory
    )
    server_token: pydantic.SecretStr = pydantic.Field(
        default_factory=_server_token_factory
    )
    _config: SimvueConfiguration = pydantic.PrivateAttr(
        default=SimvueConfiguration.fetch(mode="online")
    )

    model_config: typing.ClassVar[pydantic.ConfigDict] = pydantic.ConfigDict(
        frozen=True
    )

    def search_runs(
        self,
        *,
        attributes: list[str] | None = None,
        metadata: bool = False,
        metrics: bool = False,
        alerts: bool = False,
        system_info: bool = False,
        timing_info: bool = False,
        count_limit: pydantic.PositiveInt | None = 100,
        start_index: pydantic.NonNegativeInt = 0,
        sort_by_columns: list[tuple[str, bool]] | None = None,
        string_filters: list[str] | None = None,
    ) -> "RunsFilter":
        _filter = (
            Run.filter(
                attributes=json.dumps(attributes),
                return_basic=True,
                return_system=system_info,
                return_timing=timing_info,
                return_metrics=metrics,
                return_alerts=alerts,
                return_metadata=metadata,
                sorting=[
                    dict(zip(("column", "descending"), a)) for a in sort_by_columns
                ]
                if sort_by_columns
                else None,
            )
            .limit_to(count_limit)
            .start_at_index(start_index)
            .append_filters(string_filters or [])
        )
        return _filter

    @pydantic.validate_call
    def search_folders(
        self,
        *,
        count_limit: pydantic.PositiveInt = 100,
        start_index: pydantic.NonNegativeInt = 0,
        sort_by_columns: list[tuple[str, bool]] | None = None,
        string_filters: list[str] | None = None,
    ) -> "FoldersFilter":
        _filter = (
            Folder.filter(
                sorting=[
                    dict(zip(("column", "descending"), a)) for a in sort_by_columns
                ]
                if sort_by_columns
                else None,
            )
            .limit_to(count_limit)
            .start_at_index(start_index)
            .append_filters(string_filters or [])
        )
        return _filter

    @staticmethod
    def create_dataframe_from_runs(runs: Generator[tuple[str, Run]]) -> "DataFrame":
        pass
