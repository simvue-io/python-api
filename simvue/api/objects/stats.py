"""
Simvue Stats
============

Statistics accessible to the current user.

"""

import typing

from .base import SimvueObject

__all__ = ["Stats"]


class Stats(SimvueObject):
    def __init__(self) -> None:
        self.runs = RunStatistics(self)
        self._label = "stat"
        super().__init__()

        # Stats is a singular object (i.e. identifier is not applicable)
        # set it to empty string so not None
        self._identifier = ""

    @classmethod
    def new(cls, **kwargs) -> None:
        raise AttributeError("Creation of statistics objects is not supported")

    def offline_mode(self, is_true: bool) -> None:
        if is_true:
            raise AttributeError("Statistics only available online")

    def _get_run_stats(self) -> dict[str, int]:
        return self._get_attribute("runs")

    def _get_local_staged(self) -> dict[str, typing.Any]:
        return {}

    def _get_visibility(self) -> dict[str, bool | list[str]]:
        return {}


class RunStatistics:
    def __init__(self, sv_obj: Stats) -> None:
        self._sv_obj = sv_obj

    @property
    def created(self) -> int:
        if (_created := self._sv_obj._get_run_stats().get("created")) is None:
            raise RuntimeError("Expected key 'created' in run statistics retrieval")
        return _created

    @property
    def running(self) -> int:
        if (_running := self._sv_obj._get_run_stats().get("running")) is None:
            raise RuntimeError("Expected key 'running' in run statistics retrieval")
        return _running

    @property
    def completed(self) -> int:
        if (_completed := self._sv_obj._get_run_stats().get("running")) is None:
            raise RuntimeError("Expected key 'completed' in run statistics retrieval")
        return _completed

    @property
    def data(self) -> int:
        if (_data := self._sv_obj._get_run_stats().get("running")) is None:
            raise RuntimeError("Expected key 'data' in run statistics retrieval")
        return _data
