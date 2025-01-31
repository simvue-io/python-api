"""
Simvue Stats
============

Statistics accessible to the current user.

"""

import http
import typing

from .base import SimvueObject
from simvue.api.request import get as sv_get, get_json_from_response
from simvue.api.url import URL

__all__ = ["Stats"]


class Stats(SimvueObject):
    """Class for accessing Server statistics."""

    def __init__(self) -> None:
        self.runs = RunStatistics(self)
        self._label = "stat"
        super().__init__()

        # Stats is a singular object (i.e. identifier is not applicable)
        # set it to empty string so not None
        self._identifier = ""

    @classmethod
    def new(cls, **kwargs) -> None:
        """Creation of multiple stats objects is not logical here"""
        raise AttributeError("Creation of statistics objects is not supported")

    def whoami(self) -> dict[str, str]:
        """Return the current user"""
        _url: URL = URL(self._user_config.server.url) / "whoami"
        _response = sv_get(url=f"{_url}", headers=self._headers)
        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieving current user",
        )

    def _get_run_stats(self) -> dict[str, int]:
        """Retrieve the run statistics"""
        return self._get_attribute("runs")

    def _get_local_staged(self) -> dict[str, typing.Any]:
        """No staging for stats so returns empty dict"""
        return {}

    def _get_visibility(self) -> dict[str, bool | list[str]]:
        """Visibility does not apply here"""
        return {}

    def to_dict(self) -> dict[str, typing.Any]:
        """Returns dictionary form of statistics"""
        return {"runs": self._get_run_stats()}


class RunStatistics:
    """Interface to the run section of statistics output"""

    def __init__(self, sv_obj: Stats) -> None:
        self._sv_obj = sv_obj

    @property
    def created(self) -> int:
        """Number of created runs"""
        if (_created := self._sv_obj._get_run_stats().get("created")) is None:
            raise RuntimeError("Expected key 'created' in run statistics retrieval")
        return _created

    @property
    def running(self) -> int:
        """Number of running runs"""
        if (_running := self._sv_obj._get_run_stats().get("running")) is None:
            raise RuntimeError("Expected key 'running' in run statistics retrieval")
        return _running

    @property
    def completed(self) -> int:
        """Number of completed runs"""
        if (_completed := self._sv_obj._get_run_stats().get("running")) is None:
            raise RuntimeError("Expected key 'completed' in run statistics retrieval")
        return _completed

    @property
    def data(self) -> int:
        """Data count"""
        if (_data := self._sv_obj._get_run_stats().get("running")) is None:
            raise RuntimeError("Expected key 'data' in run statistics retrieval")
        return _data
