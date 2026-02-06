"""Simvue Server Events.

Contains a class for remotely connecting to Simvue events, or defining
a new set of events given relevant arguments.

"""

import datetime
import http
import typing
from collections.abc import Generator

import pydantic

from simvue.api.request import get as sv_get
from simvue.api.request import get_json_from_response
from simvue.models import EventSet, simvue_timestamp

from .base import SimvueObject

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035


try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035

if typing.TYPE_CHECKING:
    from simvue.api.url import URL

__all__ = ["Events"]


class Events(SimvueObject):
    """Object representing a set of run events on the Simvue Server."""

    def __init__(
        self,
        *,
        _read_only: bool = True,
        _local: bool = False,
        **kwargs: object,
    ) -> None:
        self._label: str = "event"
        super().__init__(_read_only=_read_only, _local=_local, **kwargs)  # pyright: ignore[reportArgumentType]
        self._run_id: str | None = self._staging.get("run")
        self._is_set: bool = True

    @classmethod
    @pydantic.validate_call
    @typing.override
    def get(
        cls,
        run_id: str,
        *,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.PositiveInt | None = None,
        **kwargs: object,
    ) -> Generator[EventSet]:
        """Retrieve objects from the Simvue server."""
        _class_instance = cls(_read_only=True, _local=True)
        _count: int = 0

        for response in cls._get_all_objects(
            offset=offset,
            endpoint=None,
            count=count,
            run=run_id,
            expected_type=dict,
            **kwargs,
        ):
            _data = typing.cast(
                "list[dict[str, str | float | None]] | None", response.get("data")
            )
            if _data is None:
                _out_msg: str = (
                    "Expected key 'data' for retrieval "
                    f"of {_class_instance.__class__.__name__.lower()}s"
                )
                raise RuntimeError(_out_msg)

            for _entry in _data:
                yield EventSet(**_entry)  # pyright: ignore[reportArgumentType]
                _count += 1
                if count and _count > count:
                    return

    @classmethod
    @pydantic.validate_call
    @typing.override
    def new(
        cls,
        *,
        run: str,
        offline: bool = False,
        events: list[EventSet],
        **kwargs: object,
    ) -> Self:
        """Create a new Events entry on the Simvue server."""
        return cls(
            run=run,
            events=[event.model_dump() for event in events],
            _read_only=False,
            _offline=offline,
            **kwargs,  # pyright: ignore[reportArgumentType]
        )

    @override
    def _post_single(
        self,
        data: list[dict[str, object]] | dict[str, object] | None = None,
        **kwargs: object,
    ) -> dict[str, typing.Any] | list[dict[str, typing.Any]]:
        return super()._post_single(is_json=False, data=data, **kwargs)

    @override
    def _put(self, **_: object) -> dict[str, typing.Any]:
        raise NotImplementedError("Method 'put' is not available for type Events")

    @pydantic.validate_call
    def histogram(
        self,
        timestamp_begin: datetime.datetime,
        timestamp_end: datetime.datetime,
        window: int,
        filters: list[str] | None,
    ) -> list[dict[str, str | int]]:
        """Return binned data for events.

        Parameters
        ----------
        timestamp_begin : datetime.datetime
            time window start period
        timestamp_end : datetime.datetime
            time window end period
        window : int
            window for aggregation
        filters : list[str] | None
            filter results using filter expressions

        Returns
        -------
        list[dict[str, str | int]]
            histogram data from server
        """
        if timestamp_end - timestamp_begin <= datetime.timedelta(seconds=window):
            raise ValueError(
                "Invalid arguments for datetime range, "
                "value difference must be greater than window"
            )
        _url: URL = self.base_url / "histogram"
        _time_begin: str = simvue_timestamp(timestamp_begin)
        _time_end: str = simvue_timestamp(timestamp_end)
        _response = sv_get(
            url=f"{_url}",
            headers=self._headers,
            params={  # pyright: ignore[reportArgumentType]
                "run": self._run_id,
                "window": window,
                "timestamp_begin": _time_begin,
                "timestamp_end": _time_end,
            }
            | ({"filters": filters} if filters else {}),
        )
        _json_response = get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario="Retrieval of events histogram",
            response=_response,
        )
        _json_response = typing.cast("dict[str, object]", _json_response)

        _data = typing.cast(
            "list[dict[str, str | int]] | None", _json_response.get("data")
        )

        if not _data:
            raise RuntimeError("Expected key 'data' in response for histogram request.")

        return _data

    @typing.override
    def delete(self, **kwargs: object) -> dict[str, typing.Any]:
        """Event set deletion not implemented.

        Raises
        ------
        NotImplementedError
            as event set deletion not supported
        """
        raise NotImplementedError("Cannot delete event set")

    @typing.override
    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        if online_run_id := id_mapping.get(self._staging["run"]):
            self._staging["run"] = online_run_id
