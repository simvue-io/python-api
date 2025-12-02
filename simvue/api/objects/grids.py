"""
Simvue Server Grid
==================

Contains a class for remotely connecting to a Simvue grid, or defining
a new grid given relevant arguments.

"""

import http
import msgpack
import numpy
import typing

import pydantic

from simvue.api.url import URL
from simvue.models import GridMetricSet


from .base import SimvueObject, write_only
from simvue.api.request import (
    get as sv_get,
    put as sv_put,
    post as sv_post,
    get_json_from_response,
)

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

__all__ = ["Grid"]


def check_ordered_array(
    axis_ticks: list[list[float]] | numpy.ndarray,
) -> list[list[float]]:
    """Returns if array is ordered or reverse ordered."""
    if isinstance(axis_ticks, numpy.ndarray):
        axis_ticks = axis_ticks.tolist()
    for i, _array in enumerate(axis_ticks):
        _array = numpy.array(_array)
        if not numpy.all(numpy.sort(_array) == _array) or numpy.all(
            reversed(numpy.sort(_array)) == _array
        ):
            raise ValueError(f"Axis {i} has unordered values.")
    return axis_ticks


class Grid(SimvueObject):
    """Class for retrieving grids stored on the server."""

    @pydantic.validate_call
    @write_only
    def attach_metric_for_run(self, run_id: str, metric_name: str) -> None:
        """Associates a metric for a given run to this grid."""
        if self._offline:
            self._staging.setdefault("runs", [])
            self._staging["runs"].append((run_id, metric_name))
            super().commit()
            return

        _response = sv_put(
            url=f"{self.run_data_url(run_id)}",
            headers=self._headers,
            json={"metric": metric_name},
        )

        return get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=(
                f"Adding '{metric_name}' to grid "
                f"'{self._identifier}' to run '{run_id}'",
            ),
            response=_response,
        )

    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        """Operations performed when this grid is switched from offline to online mode.

        Parameters
        ----------
        id_mapping : dict[str, str]
            mapping from offline identifier to new online identifier.
        """
        _online_runs = (
            (id_mapping[run_id], metric_name)
            for run_id, metric_name in self._staging.pop("runs", [])
        )
        super().commit()
        for run_id, metric_name in _online_runs:
            try:
                self.attach_metric_for_run(run_id=run_id, metric_name=metric_name)
            except KeyError:
                raise RuntimeError("Failed to retrieve online run identifier.")

    @property
    def grid(self) -> list[list[float]]:
        return self._get_attribute("grid")

    @property
    def name(self) -> str:
        return self._get_attribute("name")

    @classmethod
    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    def new(
        cls,
        *,
        name: str,
        grid: typing.Annotated[
            list[list[float]],
            pydantic.conlist(
                pydantic.conlist(float, min_length=1), min_length=1, max_length=2
            ),
            pydantic.AfterValidator(check_ordered_array),
        ],
        labels: list[str],
        offline: bool = False,
        **kwargs,
    ) -> Self:
        """Create a new Grid on the Simvue server.

        Parameters
        ----------
        name : str
            name for this grid.
        grid : list[list[float]]
            define a grid as a list of axes containing tick values
            number of axes must be 1 or 2
        labels : list[str]
            label each of the axes defined.
        offline: bool, optional
            whether to create in offline mode, default is False.

        Returns
        -------
        Metrics
            metrics object
        """

        if len(labels) != len(grid):
            raise AssertionError(
                "Length of argument 'labels' must match first "
                f"grid dimension {len(grid)}."
            )

        return Grid(
            grid=grid,
            labels=labels,
            name=name,
            _read_only=False,
            _offline=offline,
            **kwargs,
        )

    @property
    def dimensions(self) -> tuple[int, int]:
        """Returns the grid dimensions."""
        return len(self.grid)

    def run_data_url(self, run_id: str) -> URL:
        """Returns the URL for grid data for a specific run."""
        return URL(
            f"{self._user_config.server.url}/runs/{run_id}/grids/{self._identifier}"
        )

    def run_metric_url(self, run_id: str, metric_name: str) -> URL:
        """Returns the URL for the values for a given run metric."""
        return URL(
            f"{self._user_config.server.url}/runs/{run_id}/metrics/{metric_name}/"
        )

    @pydantic.validate_call
    def get_run_metric_values(
        self, *, run_id: str, metric_name: str, step: int
    ) -> dict:
        """Retrieve values for this grid from the server for a given run at a given step.

        Parameters
        ----------
        run_id : str
            run to return grid metrics for.
        metric_name : str
            name of metric to return values for
        step : int
            time step to retrieve values for.

        Returns
        ------
        dict[str, list[dict[str, float]]
            dictionary containing values from this for the run at specified step.
        """
        _response = sv_get(
            url=f"{self.run_metric_values_url(run_id, metric_name) / 'values'}",
            headers=self._headers,
            params={"step": step},
        )

        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            expected_type=dict,
            scenario=(
                f"Retrieving '{metric_name}' grid values "
                f"for run '{self._run_id}' at step {step}",
            ),
        )

    @pydantic.validate_call
    def get_run_metric_span(self, *, run_id: str, metric_name: str) -> dict:
        """Retrieve span for this grid from the server for a given run.

        Parameters
        ----------
        run_id : str
            run to return grid metrics for.
        metric_name : str
            metric to retrieve span information for.

        Returns
        ------
        dict[str, list[dict[str, float]]
            dictionary containing span from this for the run at specified step.
        """
        _response = sv_get(
            url=f"{self.run_metric_values_url(run_id, metric_name) / 'span'}",
            headers=self._headers,
        )

        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            expected_type=dict,
            scenario=f"Retrieving grid span for run '{run_id}'",
        )

    @classmethod
    def get(
        cls,
        *_,
        **__,
    ) -> typing.Generator[tuple[str, Self | None], None, None]:
        raise NotImplementedError


class GridMetrics(SimvueObject):
    def __init__(
        self,
        _read_only: bool = True,
        _local: bool = False,
        **kwargs,
    ) -> None:
        """Initialise a GridMetrics object instance."""
        self._label = "grid_metric"
        super().__init__(_read_only=_read_only, _local=_local, **kwargs)
        self._run_id = self._staging.get("run")
        self._is_set = True

    @staticmethod
    def run_grids_endpoint(run: str | None = None) -> URL:
        """Returns the URL for grids for a specific run."""
        return URL(f"runs/{run}/metrics/")

    def _get_attribute(self, attribute: str, *default) -> typing.Any:
        return super()._get_attribute(
            attribute,
            *default,
            url=f"{self._user_config.server.url}/{self.run_grids_endpoint(self._run_id)}",
        )

    @classmethod
    @pydantic.validate_call
    def new(
        cls, *, run: str, data: list[GridMetricSet], offline: bool = False, **kwargs
    ) -> Self:
        """Create a new GridMetrics object for n-dimensional metric submission.

        Parameters
        ----------
        run: str
            identifier for the run to attach metrics to.
        data: list[GridMetricSet]
            set of tensor-based metrics to attach to run.
        offline: bool, optional
            whether to create in offline mode, default is False.

        Returns
        -------
        Metrics
            metrics object
        """
        return GridMetrics(
            run=run,
            data=[metric.model_dump() for metric in data],
            _read_only=False,
            _offline=offline,
        )

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        *,
        runs: list[str],
        metrics: list[str],
        step: pydantic.NonNegativeInt,
        spans: bool = False,
        **kwargs,
    ) -> typing.Generator[dict[str, dict[str, list[dict[str, float]]]], None, None]:
        """Retrieve tensor-metrics from the server for a given set of runs.

        Parameters
        ----------
        runs : list[str]
            list of runs to return metric values for.
        metrics : list[str]
            list of metrics to retrieve.
        step : int
            the timestep to retrieve grid metrics for
        spans : bool, optional
            return spans informations

        Yields
        ------
        dict[str,  dict[str, list[dict[str, float]]]
            metric set object containing metrics for run.
        """
        for metric in metrics:
            for run in runs:
                yield from cls._get_all_objects(
                    endpoint=f"{cls.run_grids_endpoint(run)}/{metric}/values",
                    step=step,
                    offset=None,
                    count=None,
                )

    def commit(self) -> dict | None:
        if not (_run_staging := self._staging.pop("data", None)):
            return
        return self._log_values(_run_staging)

    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        """Operations performed when this grid metrics object is switched from offline to online mode.

        Parameters
        ----------
        id_mapping : dict[str, str]
            mapping from offline identifier to new online identifier.
        """
        metrics = self._staging.pop("data", [])

        if not (run_id := id_mapping.get(self._run_id)):
            raise RuntimeError("Failed to retrieve online run identifier.")

        self._run_id = run_id

        for metric in metrics:
            if not (new_id := id_mapping.get(metric["grid"])):
                raise RuntimeError("Failed to retrieve new online identifier for grid")
            metric["grid"] = new_id
        self._log_values(metrics)

    @pydantic.validate_call
    @write_only
    def _log_values(self, metrics: list[GridMetricSet]) -> None:
        if self._offline:
            self._staging.setdefault("data", [])
            self._staging["data"] += metrics
            super().commit()
            return

        _response = sv_post(
            url=f"{self._user_config.server.url}/{self.run_grids_endpoint(self._run_id)}",
            headers=self._headers | {"Content-Type": "application/msgpack"},
            data=msgpack.packb(metrics, use_bin_type=True),
            is_json=False,
            params={},
        )

        return get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding tensor values to run '{self._run_id}'",
            response=_response,
        )
