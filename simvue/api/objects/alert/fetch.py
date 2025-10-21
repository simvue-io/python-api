"""Simvue Alert Retrieval.

To simplify case whereby user does not know the alert type associated
with an identifier, use a generic alert object.
"""

import http
import json
import typing
from collections.abc import Generator

import pydantic

from simvue.api.objects.alert.user import UserAlert
from simvue.api.objects.base import Sort
from simvue.api.request import get as sv_get
from simvue.api.request import get_json_from_response

from .base import AlertBase
from .events import EventsAlert
from .metrics import MetricsRangeAlert, MetricsThresholdAlert

AlertType = EventsAlert | UserAlert | MetricsThresholdAlert | MetricsRangeAlert


class AlertSort(Sort):
    """Sorting object for Alert retrieval."""

    @pydantic.field_validator("column")
    @classmethod
    def check_column(cls, column: str) -> str:
        """Check specified column is permitted."""
        if column and column not in ("name", "created"):
            _out_msg = f"Invalid sort column for alerts '{column}'"
            raise ValueError(_out_msg)
        return column


class Alert:
    """Generic Simvue alert retrieval class."""

    @pydantic.validate_call()
    def __new__(
        cls,
        identifier: str | None,
        *,
        _local: bool = False,
        _read_only: bool = True,
        _user_agent: str | None = None,
        _offline: bool = False,
        **kwargs: object,
    ) -> AlertType:
        """Retrieve an object representing an alert locally or on the server by id."""
        _alert_pre = AlertBase(
            identifier=identifier,
            _local=True,
            _offline=False,
            _user_agent=None,
            _read_only=True,
            **kwargs,
        )
        if (
            identifier is not None
            and identifier.startswith("offline_")
            and not _alert_pre.staging.get("source", None)
        ):
            raise RuntimeError(
                "Cannot determine Alert type - "
                "this is likely because you are attempting to reconnect "
                "to an offline alert which has already been sent to the server."
                " To fix this, use the "
                "exact Alert type instead "
                "(eg MetricThresholdAlert, MetricRangeAlert etc)."
            )
        if _alert_pre.source == "events":
            return EventsAlert(
                identifier=identifier,
                _local=_local,
                _read_only=_read_only,
                _user_agent=_user_agent,
                _offline=_offline,
                **kwargs,
            )
        if _alert_pre.source == "metrics" and _alert_pre.get_alert().get("threshold"):
            return MetricsThresholdAlert(
                identifier=identifier,
                _local=_local,
                _read_only=_read_only,
                _user_agent=_user_agent,
                _offline=_offline,
                **kwargs,
            )
        if _alert_pre.source == "metrics":
            return MetricsRangeAlert(
                identifier=identifier,
                _local=_local,
                _read_only=_read_only,
                _user_agent=_user_agent,
                _offline=_offline,
                **kwargs,
            )
        if _alert_pre.source == "user":
            return UserAlert(
                identifier=identifier,
                _local=_local,
                _read_only=_read_only,
                _user_agent=_user_agent,
                _offline=_offline,
                **kwargs,
            )

        _out_msg: str = f"Unknown source type '{_alert_pre.source}'"
        raise RuntimeError(_out_msg)

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        *,
        offline: bool = False,
        count: int | None = None,
        offset: int | None = None,
        sorting: list[AlertSort] | None = None,
        **kwargs: str | float | None | list[str],
    ) -> Generator[tuple[str, AlertType]]:
        """Fetch all alerts from the server for the current user.

        Parameters
        ----------
        count : int, optional
            limit the number of results, default of None returns all.
        offset : int, optional
            start index for returned results, default of None starts at 0.
        sorting : list[dict] | None, optional
            list of sorting definitions in the form {'column': str, 'descending': bool}

        Yields
        ------
        tuple[str, AlertType]
            identifier for an alert
            the alert itself as a class instance
        """
        if offline:
            return

        # Currently no alert filters
        _ = kwargs.pop("filters", None)

        _class_instance = AlertBase(_local=True, _read_only=True)
        _url = f"{_class_instance.base_url}"
        _params: dict[str, int | str | None] = {"start": offset, "count": count}

        if sorting:
            _params["sorting"] = json.dumps([sort.to_params() for sort in sorting])

        _response = sv_get(
            _url,
            headers=_class_instance.headers,
            params=_params | kwargs,
        )

        _label: str = _class_instance.__class__.__name__.lower()
        _label = _label.replace("base", "")
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {_label}s",
        )
        _json_response = typing.cast(
            "dict[str, list[dict[str, object]]]", _json_response
        )

        if (_data := _json_response.get("data")) is None:
            _out_msg: str = f"Expected key 'data' for retrieval of {_label}s"
            raise RuntimeError(_out_msg)

        _out_dict: dict[str, AlertType] = {}

        for _entry in _json_response["data"]:
            _id = typing.cast("str", _entry.pop("id"))
            if _entry["source"] == "events":
                yield (
                    _id,
                    EventsAlert(
                        _read_only=True,
                        identifier=_id,
                        _local=True,
                        _offline=False,
                        _user_agent=None,
                        **_entry,
                    ),
                )
            elif _entry["source"] == "user":
                yield (
                    _id,
                    UserAlert(
                        _read_only=True,
                        identifier=_id,
                        _local=True,
                        _offline=False,
                        _user_agent=None,
                        **_entry,
                    ),
                )
            elif (
                _entry["source"] == "metrics"
                and _entry.get("alert", {}).get("threshold") is not None  # pyright: ignore[reportAttributeAccessIssue]
            ):
                yield (
                    _id,
                    MetricsThresholdAlert(
                        _local=True,
                        _read_only=True,
                        identifier=_id,
                        _offline=False,
                        _user_agent=None,
                        **_entry,
                    ),
                )
            elif (
                _entry["source"] == "metrics"
                and _entry.get("alert", {}).get("range_low") is not None  # pyright: ignore[reportAttributeAccessIssue]
            ):
                yield (
                    _id,
                    MetricsRangeAlert(
                        _local=True, _read_only=True, identifier=_id, **_entry
                    ),
                )
            else:
                _out_msg = (
                    f"Unrecognised alert source '{_entry['source']}'"
                    f" with data '{_entry}'"
                )
                raise RuntimeError(_out_msg)
