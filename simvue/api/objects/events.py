"""
Simvue Server Events
====================

Contains a class for remotely connecting to Simvue events, or defining
a new set of events given relevant arguments.

"""

import http
import typing
import datetime

import pydantic

from simvue.api.url import URL

from .base import SimvueObject
from simvue.models import DATETIME_FORMAT, EventSet
from simvue.api.request import get as sv_get, get_json_from_response

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

__all__ = ["Events"]


class Events(SimvueObject):
    def __init__(
        self,
        _read_only: bool = True,
        _local: bool = False,
        **kwargs,
    ) -> None:
        self._label = "event"
        super().__init__(_read_only=_read_only, _local=_local, **kwargs)
        self._run_id = self._staging.get("run")

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        run_id: str,
        *,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.PositiveInt | None = None,
        **kwargs,
    ) -> typing.Generator[EventSet, None, None]:
        _class_instance = cls(_read_only=True, _local=True)
        _count: int = 0

        for response in cls._get_all_objects(offset, count=count, run=run_id, **kwargs):
            if (_data := response.get("data")) is None:
                raise RuntimeError(
                    f"Expected key 'data' for retrieval of {_class_instance.__class__.__name__.lower()}s"
                )

            for _entry in _data:
                yield EventSet(**_entry)
                _count += 1
                if _count > count:
                    return

    @classmethod
    @pydantic.validate_call
    def new(
        cls, *, run: str, offline: bool = False, events: list[EventSet], **kwargs
    ) -> Self:
        """Create a new Events entry on the Simvue server"""
        return Events(
            run=run,
            events=[event.model_dump() for event in events],
            _read_only=False,
            _offline=offline,
            **kwargs,
        )

    def _post(self, **kwargs) -> dict[str, typing.Any]:
        return super()._post(is_json=False, **kwargs)

    def _put(self, **kwargs) -> dict[str, typing.Any]:
        raise NotImplementedError("Method 'put' is not available for type Events")

    @pydantic.validate_call
    def histogram(
        self,
        timestamp_begin: datetime.datetime,
        timestamp_end: datetime.datetime,
        window: int,
        filters: list[str] | None,
    ) -> list[dict[str, str | int]]:
        if timestamp_end - timestamp_begin <= datetime.timedelta(seconds=window):
            raise ValueError(
                "Invalid arguments for datetime range, "
                "value difference must be greater than window"
            )
        _url: URL = self._base_url / "histogram"
        _time_begin: str = timestamp_begin.strftime(DATETIME_FORMAT)
        _time_end: str = timestamp_end.strftime(DATETIME_FORMAT)
        _response = sv_get(
            url=_url,
            headers=self._headers,
            params={
                "run": self._run_id,
                "window": window,
                "timestamp_begin": timestamp_begin,
                "timestamp_end": timestamp_end,
            }
            | ({"filters": filters} if filters else {}),
        )
        _json_response = get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieval of events histogram",
            response=_response,
        )
        return _json_response.get("data")

    def delete(self, **kwargs) -> dict[str, typing.Any]:
        """Event set deletion not implemented.

        Raises
        ------
        NotImplementedError
            as event set deletion not supported
        """
        raise NotImplementedError("Cannot delete event set")

    def on_reconnect(self, id_mapping: dict[str, str]):
        if online_run_id := id_mapping.get(self._staging["run"]):
            self._staging["run"] = online_run_id
