"""Simvue Server Grid.

Contains a class for remotely connecting to a Simvue grid, or defining
a new grid given relevant arguments.

"""

import http
import typing
from collections.abc import Generator

import msgpack
import numpy as np
import pydantic

from simvue.api.request import (
    get as sv_get,
)
from simvue.api.request import (
    get_json_from_response,
)
from simvue.api.request import (
    post as sv_post,
)
from simvue.api.request import (
    put as sv_put,
)
from simvue.api.url import URL
from simvue.models import GridMetricSet

from .base import SimvueObject, write_only

try:
    from typing import Self, override
except ImportError:
    from typing import Self, override

__all__ = ["Grid"]


def check_ordered_array(
    axis_ticks: list[list[float]] | np.ndarray,
) -> list[list[float]]:
    """Return if array is ordered or reverse ordered."""
    if isinstance(axis_ticks, np.ndarray):
        axis_ticks = axis_ticks.tolist()
    for i, _array in enumerate(axis_ticks):
        _array = np.array(_array)
        if not np.all(np.sort(_array) == _array) or np.all(
            reversed(np.sort(_array)) == _array
        ):
            _out_msg: str = f"Axis {i} has unordered values."
            raise ValueError(_out_msg)
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
            return None

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

    @override
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
            except KeyError as e:
                raise RuntimeError("Failed to retrieve online run identifier.") from e

    @property
    def grid(self) -> list[list[float]]:
        """Return the grid as list."""
        return self._get_attribute("grid")

    @property
    def name(self) -> str:
        """Retrieve the name."""
        return self._get_attribute("name")

    @classmethod
    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    @override
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
        **kwargs: object,
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
            _out_msg = (
                "Length of argument 'labels' must match first "
                f"grid dimension {len(grid)}."
            )
            raise AssertionError(_out_msg)

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
        """Return the URL for grid data for a specific run."""
        return URL(
            f"{self._user_config.server.url}/runs/{run_id}/grids/{self._identifier}"
        )

    def run_metric_url(self, run_id: str, metric_name: str) -> URL:
        """Return the URL for the values for a given run metric."""
        return URL(
            f"{self._user_config.server.url}/runs/{run_id}/metrics/{metric_name}/"
        )

    @pydantic.validate_call
    def get_run_metric_values(
        self, *, run_id: str, metric_name: str, step: int
    ) -> dict[str, str | float | list[object]]:
        """Retrieve grid values from the server for a given run at a given step.

        Parameters
        ----------
        run_id : str
            run to return grid metrics for.
        metric_name : str
            name of metric to return values for
        step : int
            time step to retrieve values for.

        Returns
        -------
        dict[str, str | float | list[object]]
            dictionary containing values from this Grid for the run at specified step.
        """
        _response = sv_get(
            url=f"{self.run_metric_url(run_id, metric_name) / 'values'}",
            headers=self._headers,
            params={"step": step},
        )

        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            expected_type=dict,
            scenario=(
                f"Retrieving '{metric_name}' grid values "
                f"for run '{run_id}' at step {step}",
            ),
        )

    @pydantic.validate_call
    def get_run_metric_span(
        self, *, run_id: str, metric_name: str
    ) -> dict[str, int | float | str]:
        """Retrieve span for this grid from the server for a given run.

        Parameters
        ----------
        run_id : str
            run to return grid metrics for.
        metric_name : str
            metric to retrieve span information for.

        Returns
        -------
        dict[str, list[dict[str, float]]
            dictionary containing span from this for the run at specified step.
        """
        _response = sv_get(
            url=f"{self.run_metric_url(run_id, metric_name) / 'span'}",
            headers=self._headers,
        )

        _response = typing.cast(
            "list[dict[str, int | float | str]]",
            get_json_from_response(
                response=_response,
                expected_status=[http.HTTPStatus.OK],
                expected_type=list,
                scenario=f"Retrieving grid span for run '{run_id}'",
            ),
        )

        if not _response:
            raise RuntimeError("Failed to retrieve span, no data.")

        return _response[0]

    @classmethod
    @override
    def get(
        cls,
        *_: object,
        **__: object,
    ) -> Generator[tuple[str, Self | None]]:
        raise NotImplementedError


class GridMetrics(SimvueObject):
    def __init__(
        self,
        *,
        _read_only: bool = True,
        _local: bool = False,
        **kwargs: object,
    ) -> None:
        """Initialise a GridMetrics object instance."""
        self._label = "grid_metric"
        super().__init__(_read_only=_read_only, _local=_local, **kwargs)
        self._run_id = self._staging.get("run")
        self._is_set = True

    @staticmethod
    def run_grids_endpoint(run: str | None = None) -> URL:
        """Return the URL for grids for a specific run."""
        return URL(f"runs/{run}/metrics/")

    @override
    def _get_attribute(self, attribute: str, *default: object) -> typing.Any:
        return super()._get_attribute(
            attribute,
            *default,
            url=f"{self._user_config.server.url}/{self.run_grids_endpoint(self._run_id)}",
        )

    @classmethod
    @pydantic.validate_call
    @override
    def new(
        cls,
        *,
        run: str,
        data: list[GridMetricSet],
        offline: bool = False,
        **kwargs: object,
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
    @override
    def get(
        cls,
        *,
        runs: list[str],
        metrics: list[str],
        step: pydantic.NonNegativeInt,
        **kwargs: object,
    ) -> Generator[dict[str, dict[str, list[dict[str, float]]]]]:
        """Retrieve tensor-metrics from the server for a given set of runs.

        Parameters
        ----------
        runs : list[str]
            list of runs to return metric values for.
        metrics : list[str]
            list of metrics to retrieve.
        step : int
            the timestep to retrieve grid metrics for

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

    @override
    def commit(self) -> dict[str, object] | None:
        if not (_run_staging := self._staging.pop("data", None)):
            return None
        return self._log_values(_run_staging)

    @override
    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        """Operations performed when object is switched from offline to online mode.

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
            return None

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
