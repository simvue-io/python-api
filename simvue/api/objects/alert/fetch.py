"""
Simvue Alert Retrieval
======================

To simplify case whereby user does not know the alert type associated
with an identifier, use a generic alert object.
"""

import typing
import http

import pydantic

from simvue.api.objects.alert.user import UserAlert
from simvue.api.request import get_json_from_response
from simvue.api.request import get as sv_get
from .events import EventsAlert
from .metrics import MetricsThresholdAlert, MetricsRangeAlert
from .base import AlertBase

AlertType = EventsAlert | UserAlert | MetricsThresholdAlert | MetricsRangeAlert


class Alert:
    """Generic Simvue alert retrieval class"""

    @pydantic.validate_call()
    def __new__(cls, identifier: str, **kwargs) -> AlertType:
        """Retrieve an object representing an alert either locally or on the server by id"""
        _alert_pre = AlertBase(identifier=identifier, **kwargs)
        if (
            identifier is not None
            and identifier.startswith("offline_")
            and not _alert_pre._staging.get("source", None)
        ):
            raise RuntimeError(
                "Cannot determine Alert type - this is likely because you are attempting to reconnect "
                "to an offline alert which has already been sent to the server. To fix this, use the "
                "exact Alert type instead (eg MetricThresholdAlert, MetricRangeAlert etc)."
            )
        if _alert_pre.source == "events":
            return EventsAlert(identifier=identifier, **kwargs)
        elif _alert_pre.source == "metrics" and _alert_pre.get_alert().get("threshold"):
            return MetricsThresholdAlert(identifier=identifier, **kwargs)
        elif _alert_pre.source == "metrics":
            return MetricsRangeAlert(identifier=identifier, **kwargs)
        elif _alert_pre.source == "user":
            return UserAlert(identifier=identifier, **kwargs)

        raise RuntimeError(f"Unknown source type '{_alert_pre.source}'")

    @classmethod
    def get(
        cls,
        offline: bool = False,
        count: int | None = None,
        offset: int | None = None,
        **kwargs,
    ) -> typing.Generator[tuple[str, AlertType], None, None]:
        """Fetch all alerts from the server for the current user.

        Parameters
        ----------
        count : int, optional
            limit the number of results, default of None returns all.
        offset : int, optional
            start index for returned results, default of None starts at 0.

        Yields
        ------
        tuple[str, AlertType]
            identifier for an alert
            the alert itself as a class instance
        """
        if offline:
            return

        # Currently no alert filters
        kwargs.pop("filters", None)

        _class_instance = AlertBase(_local=True, _read_only=True)
        _url = f"{_class_instance._base_url}"

        _response = sv_get(
            _url,
            headers=_class_instance._headers,
            params={"start": offset, "count": count} | kwargs,
        )

        _label: str = _class_instance.__class__.__name__.lower()
        _label = _label.replace("base", "")
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {_label}s",
        )

        if (_data := _json_response.get("data")) is None:
            raise RuntimeError(f"Expected key 'data' for retrieval of {_label}s")

        _out_dict: dict[str, AlertType] = {}

        for _entry in _json_response["data"]:
            _id = _entry.pop("id")
            if _entry["source"] == "events":
                yield (
                    _id,
                    EventsAlert(_read_only=True, identifier=_id, _local=True, **_entry),
                )
            elif _entry["source"] == "user":
                yield (
                    _id,
                    UserAlert(_read_only=True, identifier=_id, _local=True, **_entry),
                )
            elif _entry["source"] == "metrics" and _entry.get("alert", {}).get(
                "threshold"
            ):
                yield (
                    _id,
                    MetricsThresholdAlert(
                        _local=True, _read_only=True, identifier=_id, **_entry
                    ),
                )
            elif _entry["source"] == "metrics" and _entry.get("alert", {}).get(
                "range_low"
            ):
                yield (
                    _id,
                    MetricsRangeAlert(
                        _local=True, _read_only=True, identifier=_id, **_entry
                    ),
                )
            else:
                raise RuntimeError(f"Unrecognised alert source '{_entry['source']}'")
