"""
Simvue Server Grid
==================

Contains a class for remotely connecting to a Simvue grid, or defining
a new grid given relevant arguments.

"""

import http
import numpy
import json
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


def check_ordered_array(array: numpy.ndarray) -> bool:
    """Returns if array is ordered or reverse ordered."""
    if array.ndim != 1:
        raise ValueError("Ordering can only be checked on a 1D array")
    return numpy.all(numpy.sort(array) == array) or numpy.all(
        numpy.reversed(numpy.sort(array)) == array
    )


class Grid(SimvueObject):
    """Class for retrieving grids stored on the server."""

    @pydantic.validate_call
    @write_only
    def attach_to_run(self, run_id: str) -> None:
        """Attach this grid to a given run."""
        _response = sv_put(
            url=f"{self.run_data_url(run_id)}",
            headers=self._headers,
        )

        return get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding grid '{self.name}' to run '{run_id}'",
            response=_response,
        )

    @property
    def grid(self) -> list[list[float]]:
        return self._get_attribute("grid")

    @classmethod
    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    def new(
        cls,
        *,
        name: str,
        grid: numpy.ndarray,
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
            define a grid as a list of axes containing tick values.
        labels : list[str]
            label each of the axes defined.
        offline: bool, optional
            whether to create in offline mode, default is False.

        Returns
        -------
        Metrics
            metrics object
        """
        if not len(grid.shape) > 0:
            raise ValueError("Invalid argument for 'grid'")

        if len(labels) != len(set(labels)):
            raise ValueError("Labels must be unique.")

        if len(labels) != grid.shape[0]:
            raise AssertionError(
                "Length of argument 'labels' must match first "
                f"grid dimension {grid.shape[0]}."
            )

        for i, axis in enumerate(grid):
            if not check_ordered_array(axis):
                raise ValueError(f"Axis {i} has unordered values.")

        return Grid(
            grid=grid.tolist(),
            labels=labels,
            name=name,
            _read_only=False,
            _offline=offline,
        )

    @property
    def dimensions(self) -> tuple[int, int]:
        """Returns the grid dimensions."""
        return numpy.array(self.grid).shape

    @classmethod
    def run_data_url(self, run_id: str) -> URL:
        """Returns the URL for grid data for a specific run."""
        return URL(
            f"{self._user_config.server.url}/runs/{run_id}/grids/{self._identifier}"
        )

    @pydantic.validate_call
    def get_run_values(self, step: int) -> dict:
        """Retrieve values for this grid from the server for a given run at a given step.

        Parameters
        ----------
        run_id : str
            run to return grid metrics for.
        step : int
            time step to retrieve values for.

        Returns
        ------
        dict[str, list[dict[str, float]]
            dictionary containing values from this for the run at specified step.
        """
        _response = sv_get(
            url=f"{self.run_data_url / 'values'}",
            headers=self._headers,
            params={"step": step},
        )

        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            expected_type=dict,
            scenario=f"Retrieving grid values for run '{self._run_id}' at step {step}",
        )

    @pydantic.validate_call
    def get_run_span(self, run_id: str) -> dict:
        """Retrieve span for this grid from the server for a given run.

        Parameters
        ----------
        run_id : str
            run to return grid metrics for.

        Returns
        ------
        dict[str, list[dict[str, float]]
            dictionary containing span from this for the run at specified step.
        """
        _response = sv_get(
            url=f"{self.run_data_url / 'span'}",
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
        self._label = "grid"
        super().__init__(_read_only=_read_only, _local=_local, **kwargs)
        self._run_id = self._staging.get("run")
        self._is_set = True

    @property
    @staticmethod
    def run_grids_endpoint(run: str | None = None) -> URL:
        """Returns the URL for grids for a specific run."""
        return URL(f"runs/{run}/grids/")

    def _get_attribute(self, attribute: str, *default) -> typing.Any:
        return super()._get_attribute(
            attribute,
            *default,
            url=f"{self._user_config.server.url / self.run_grids_endpoint(self._run_id)}",
        )

    @classmethod
    @pydantic.validate_call
    def new(
        cls, *, run: str, metrics: list[GridMetricSet], offline: bool = False, **kwargs
    ) -> Self:
        """Create a new GridMetrics object for n-dimensional metric submission.

        Parameters
        ----------
        run: str
            identifier for the run to attach metrics to.
        metrics: list[GridMetricSet]
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
            metrics=[metric.model_dump() for metric in metrics],
            _read_only=False,
            _offline=offline,
        )

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        runs: list[str],
        *,
        spans: bool = False,
        **kwargs,
    ) -> typing.Generator[dict[str, dict[str, list[dict[str, float]]]], None, None]:
        """Retrieve tensor-metrics from the server for a given set of runs.

        Parameters
        ----------
        runs : list[str]
            list of runs to return metrics for.
        spans : bool, optional
            return spans information

        Yields
        ------
        dict[str,  dict[str, list[dict[str, float]]]
            metric set object containing metrics for run.
        """
        for run in runs:
            yield from cls._get_all_objects(
                runs=json.dumps(runs),
                endpoint=cls.run_grids_endpoint(run),
                **kwargs,
            )

    def commit(self) -> dict | None:
        _run_staging = self._staging.pop("values", None)
        self._log_values(self._staging["metrics"])

    @staticmethod
    def group_metrics_by_grid(
        metric_list: list[GridMetricSet],
    ) -> dict[str, list[GridMetricSet]]:
        groups: dict[str, list[GridMetricSet]] = {}
        for metric in metric_list:
            groups.setdefault(metric.grid_identifier, [])
            groups[metric.grid_identifier].append(metric)
        return groups

    @pydantic.validate_call
    @write_only
    @classmethod
    def _log_values(self, metrics: list[GridMetricSet]) -> None:
        # FIXME: Having to sort metrics before sending them is a bottleneck
        # require server endpoint for sending metrics for multiple grids at once
        # temporary work around is to sort metrics into grids
        for grid_id, metric_set in self.group_metrics_by_grid(metrics).items():
            _response = sv_post(
                url=f"{self._base_url}/{grid_id}",
                headers=self._headers,
                body={
                    "run": self._run_id,
                    "metrics": metric_set,
                },
            )

        get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding values to grid '{grid_id}' for run '{self._run_id}'",
            response=_response,
        )
