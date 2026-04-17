"""Fetch Objects from the Simvue Server."""

import json
import simvue.api.objects as sv_obj
import pydantic as pyd
import typing

from collections.abc import Generator
from simvue.exception import InvalidQueryError
from simvue.models import MetricKeyString, ObjectID, XAxis, PerRunMetrics


@pyd.validate_call
def get_metric_values(
    *,
    metric_names: typing.Annotated[
        list[MetricKeyString], pyd.conlist(str, min_length=1)
    ],
    x_axis: XAxis,
    run_ids: list[ObjectID] | None = None,
    run_filters: list[str] | None = None,
    server_url: pyd.HttpUrl | None = None,
    server_token: pyd.SecretStr | None = None,
) -> Generator[tuple[ObjectID, PerRunMetrics]]:
    """Retrieve all metric values for a given metric set and runs.

    Parameters
    ----------
    metric_names : list[str]
        list of metrics to retrieve by name
    x_axis : Literal['step', 'time', 'timestamp']
        xaxis value to use for metrics
    run_ids : list[str] | None, optional
        list of runs by ID to retrieve data for,
        if None then `run_filters` must be specified.
    run_filters : list[str] | None, optional
        list of filters to use for selecting runs for
        data retrieval, if None then `run_ids` must be specified.
    server_url : str | None, optional
        alternative server URL to use for item retrieval
    server_token : str | None, optional
        token for the alternative URL

    Yields
    ------
    str
        Run identifier
    dict[str, list[dict[str, float]]]
        Metric values for each run at all time intervals
    """
    if server_url and not server_token:
        raise ValueError("A token must be provided for the alternative URL")

    if (not run_ids and not run_filters) or (run_ids and run_filters):
        raise InvalidQueryError(
            "Argument must be provided for either 'run_ids' or 'run_filters', "
            + "but not both."
        )
    _query_arguments: dict[str, object] = {
        "xaxis": x_axis,
        "metrics": metric_names,
    }

    if run_filters:
        _run_list: list[str] = []
        _server_args: dict[str, str | None] = {
            "server_url": server_url.encoded_string() if server_url else None,
            "server_token": server_token.get_secret_value() if server_token else None,
        }
        for run_id in sv_obj.Run.ids(filters=json.dumps(run_filters), **_server_args):
            _run_list.append(run_id)
            if len(_run_list) > 99:
                for result in sv_obj.Metrics.get(
                    runs=_run_list, metrics=metric_names, xaxis=x_axis, **_server_args
                ):
                    yield from result.items()
                _run_list = []
        if _run_list:
            for result in sv_obj.Metrics.get(
                runs=_run_list, metrics=metric_names, xaxis=x_axis, **_server_args
            ):
                yield from result.items()

    if run_ids:
        for result in sv_obj.Metrics.get(
            runs=run_ids, metrics=metric_names, xaxis=x_axis
        ):
            yield from result.items()
