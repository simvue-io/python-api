"""
Simvue Server Metrics
=====================

Contains a class for remotely connecting to Simvue metrics, or defining
a new set of metrics given relevant arguments.

"""

import http
import typing
import json

import pydantic


from .base import SimvueObject
from simvue.models import MetricSet
from simvue.api.request import get as sv_get, get_json_from_response

__all__ = ["Metrics"]


class Metrics(SimvueObject):
    def __init__(
        self,
        _read_only: bool = True,
        _local: bool = False,
        **kwargs,
    ) -> None:
        self._label = "metric"
        super().__init__(_read_only=_read_only, _local=_local, **kwargs)
        self._run_id = self._staging.get("run")

    @classmethod
    @pydantic.validate_call
    def new(
        cls, *, run: str, offline: bool = False, metrics: list[MetricSet], **kwargs
    ):
        """Create a new Events entry on the Simvue server"""
        _metrics = Metrics(
            run=run,
            metrics=[metric.model_dump() for metric in metrics],
            _read_only=False,
            **kwargs,
        )
        _metrics.offline_mode(offline)
        return _metrics

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        metrics: list[str],
        xaxis: typing.Literal["timestamp", "step", "time"],
        *,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.PositiveInt | None = None,
        **kwargs,
    ) -> typing.Generator[MetricSet, None, None]:
        _class_instance = cls(_read_only=True, _local=True)
        if (
            _data := cls._get_all_objects(
                count,
                offset,
                metrics=json.dumps(metrics),
                xaxis=xaxis,
                **kwargs,
            ).get("data")
        ) is None:
            raise RuntimeError(
                f"Expected key 'data' for retrieval of {_class_instance.__class__.__name__.lower()}s"
            )

        for _entry in _data:
            yield MetricSet(**_entry)

    @pydantic.validate_call
    def span(self, run_ids: list[str]) -> dict[str, int | float]:
        """Returns the metrics span for the given runs"""
        _url = self._base_url / "span"
        _response = sv_get(url=f"{_url}", headers=self._headers, json=run_ids)
        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieving metric spans",
        )

    @pydantic.validate_call
    def names(self, run_ids: list[str]) -> list[str]:
        """Returns the metric names for the given runs"""
        _url = self._base_url / "names"
        _response = sv_get(
            url=f"{_url}", headers=self._headers, params={"runs": json.dumps(run_ids)}
        )
        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieving metric names",
            expected_type=list,
        )

    def _post(self, **kwargs) -> dict[str, typing.Any]:
        return super()._post(is_json=False, **kwargs)

    def delete(
        self, _linked_objects: list[str] | None = None, **kwargs
    ) -> dict[str, typing.Any]:
        raise NotImplementedError("Cannot delete metric set")

    def on_reconnect(self, offline_to_online_id_mapping: dict[str, str]):
        if online_run_id := offline_to_online_id_mapping.get(self._staging["run"]):
            self._staging["run"] = online_run_id
