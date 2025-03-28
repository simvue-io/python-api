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

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

__all__ = ["Metrics"]


class Metrics(SimvueObject):
    """Class for retrieving metrics stored on the server."""

    def __init__(
        self,
        _read_only: bool = True,
        _local: bool = False,
        **kwargs,
    ) -> None:
        """Initialise a Metrics object instance."""
        self._label = "metric"
        super().__init__(_read_only=_read_only, _local=_local, **kwargs)
        self._run_id = self._staging.get("run")

    @classmethod
    @pydantic.validate_call
    def new(
        cls, *, run: str, metrics: list[MetricSet], offline: bool = False, **kwargs
    ) -> Self:
        """Create a new Metrics entry on the Simvue server.

        Parameters
        ----------
        run: str
            identifier for the run to attach metrics to.
        metrics: list[MetricSet]
            set of metrics to attach to run.
        offline: bool, optional
            whether to create in offline mode, default is False.

        Returns
        -------
        Metrics
            metrics object
        """
        return Metrics(
            run=run,
            metrics=[metric.model_dump() for metric in metrics],
            _read_only=False,
            _offline=offline,
        )

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        metrics: list[str],
        xaxis: typing.Literal["timestamp", "step", "time"],
        runs: list[str],
        *,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.PositiveInt | None = None,
        **kwargs,
    ) -> typing.Generator[dict[str, dict[str, list[dict[str, float]]]], None, None]:
        """Retrieve metrics from the server for a given set of runs.

        Parameters
        ----------
        metrics: list[str]
            name of metrics to retrieve.
        xaxis : Literal["step", "time", "timestamp"]
            the x-axis type
                * step - enumeration.
                * time - time in seconds.
                * timestamp - time stamp.
        runs : list[str]
            list of runs to return metrics for.
        count : int | None, optional
            limit result count.
        offset : int | None, optional
            index offset for count.

        Yields
        ------
        dict[str,  dict[str, list[dict[str, float]]]
            metric set object containing metrics for run.
        """
        yield from cls._get_all_objects(
            offset,
            metrics=json.dumps(metrics),
            runs=json.dumps(runs),
            xaxis=xaxis,
            count=count,
            **kwargs,
        )

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

    def delete(self, **kwargs) -> dict[str, typing.Any]:
        """Metrics cannot be deleted"""
        raise NotImplementedError("Cannot delete metric set")

    def on_reconnect(self, id_mapping: dict[str, str]):
        """Action performed when mode switched from offline to online.

        Parameters
        ----------
        id_mapping : dict[str, str]
            mapping from offline to online identifier.

        """
        if online_run_id := id_mapping.get(self._staging["run"]):
            self._staging["run"] = online_run_id

    def to_dict(self) -> dict[str, typing.Any]:
        """Convert metrics object to dictionary.

        Returns
        -------
        dict[str, Any]
            dictionary representation of metrics object.
        """
        return self._staging
