"""
Simvue Server Grid
==================

Contains a class for remotely connecting to a Simvue grid, or defining
a new grid given relevant arguments.

"""

import http
import numpy
import typing

import pydantic

from simvue.api.url import URL


from .base import SimvueObject
from simvue.api.request import get as sv_get, put as sv_put, get_json_from_response

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

    @classmethod
    @pydantic.validate_call
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
            grid=grid,
            labels=labels,
            name=name,
            _read_only=False,
            _offline=offline,
        )

    @property
    def dimensions(self) -> tuple[int, int]:
        """Returns the grid dimensions."""
        return numpy.array(self.grid).shape

    def run_data_url(self, run_id: str) -> URL:
        """Returns the URL for grid data for a specific run."""
        return URL(
            f"{self._user_config.server.url}/runs/{run_id}/grids/{self._identifier}"
        )

    @pydantic.validate_call
    def get_run_values(self, run_id: str, step: int) -> dict:
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
            url=f"{self.run_data_url(run_id) / 'values'}",
            headers=self._headers,
            params={"step": step},
        )

        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            expected_type=dict,
            scenario=f"Retrieving grid values for run '{run_id}' at step {step}",
        )

    @pydantic.validate_call
    def attach_to_run(self, run_id: str) -> None:
        """Attach this grid to a given run.

        Parameters
        ----------
        run_id : str
            identifier of run to associate this artifact with.
        """
        if self._offline:
            self._staging["runs"] = self._init_data["runs"]
            super().commit()
            return

        _response = sv_put(
            url=f"{self.run_data_url(run_id)}",
            headers=self._headers,
        )

        get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding grid '{self.name}' to run '{run_id}'",
            response=_response,
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
            url=f"{self.run_data_url(run_id) / 'span'}",
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
