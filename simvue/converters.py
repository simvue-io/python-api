"""Converter Functions.

Contains functions for converting objects retrieved from the server between
data types including creation of DataFrames for metrics
"""

from __future__ import annotations

import typing

import flatdict
import pandas as pd

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from pandas import DataFrame


def aggregated_metrics_to_dataframe(
    request_response_data: dict[str, object],
    xaxis: str,
    parse_to: typing.Literal["dict", "dataframe"] = "dict",
) -> DataFrame | dict[str, dict[tuple[float, str], float | None]]:
    """Create data frame for an aggregate of metrics.

    Returns a dataframe with columns being metrics and sub-columns being the
    minimum, average etc.

    Parameters
    ----------
    request_response_data : dict[str, list[dict[str, float]]]
        the data retrieved from the Simvue server
    xaxis : str
        the x-axis label
    parse_to : Literal["dict", "dataframe"], optional
        form of output
            * dict - dictionary of values.
            * dataframe - dataframe (pd must be installed).

    Returns
    -------
    DataFrame | dict
        a pd dataframe of the metric set or the data as a dictionary
    """
    _all_steps: list[float] = sorted(
        {
            d[xaxis]
            for sublist in request_response_data.values()
            for d in sublist
            if xaxis in d
        }
    )

    # Get the keys from the aggregate which are not the xaxis label
    _first_metric_set = next(iter(request_response_data.values()))
    _value_types = next(iter(_first_metric_set)).keys()
    _value_types = list(_value_types)
    _value_types.remove(xaxis)

    result_dict: dict[str, dict[tuple[float, str], float | None]] = {
        metric_name: {} for metric_name in request_response_data
    }

    for metric_name, metrics in request_response_data.items():
        metrics_iterator = iter(metrics)
        _metric_steps = (d[xaxis] for d in metrics)
        for step in _all_steps:
            if step not in _metric_steps:
                for value_type in _value_types:
                    result_dict[metric_name][step, value_type] = None
            else:
                next_item = next(metrics_iterator)
                for value_type in _value_types:
                    result_dict[metric_name][step, value_type] = next_item.get(
                        value_type
                    )

    if parse_to == "dataframe":
        _data_frame = pd.DataFrame(result_dict)
        _data_frame.index.name = xaxis
        return _data_frame
    if parse_to == "dict":
        return result_dict
    _out_msg: str = "Unrecognised parse format '{parse_to}'"
    raise ValueError(_out_msg)


def parse_run_set_metrics(
    request_response_data: dict[str, object],
    xaxis: str,
    run_labels: list[str],
    parse_to: typing.Literal["dict", "dataframe"] = "dict",
) -> dict[str, dict[tuple[float, str], float | None]] | None | DataFrame:
    """Parse JSON response metric data from the server into the specified form.

    Creates either a dictionary or a pd dataframe of the data collected
    from multiple runs and metrics

    Parameters
    ----------
    request_response_data: dict[str, dict[str, list[dict[str, float]]]]
        JSON response data
    xaxis : str
        the x-axis label/key
    run_labels : list[str]
        the labels to assign for the runs
    parse_to : Literal["dict", "dataframe"], optional
        form in which to parse data
            * dict - return a values dictionary (default).
            * dataframe - assembled into dataframe (requires pd).

    Returns
    -------
    dict[str, dict[tuple[float, str], float]] | None | DataFrame
        either a dictionary or pd DataFrame containing the results

    Raises
    ------
    ValueError
        if an unrecognised parse format is specified
    """
    if not request_response_data:
        return pd.DataFrame({}) if parse_to == "dataframe" else {}

    _all_steps: list[float] = sorted(
        {
            d[xaxis]
            for run_data in request_response_data.values()
            for sublist in run_data.values()
            for d in sublist
            if xaxis in d
        }
    )

    _all_metrics: list[str] = sorted(
        {key for run_data in request_response_data.values() for key in run_data}
    )

    # Get the keys from the aggregate which are not the xaxis label
    _first_run = next(iter(request_response_data.values()))
    _first_metric_set = next(iter(_first_run.values()))
    _value_types = next(iter(_first_metric_set)).keys()
    _value_types = list(_value_types)
    _value_types.remove(xaxis)

    _result_dict: dict[str, dict[tuple[float, str], float | None]] = {
        metric_name: {} for metric_name in _all_metrics
    }

    for run_label, run_data in zip(
        run_labels, request_response_data.values(), strict=False
    ):
        for metric_name in _all_metrics:
            if metric_name not in run_data:
                for step in _all_steps:
                    _result_dict[metric_name][step, run_label] = None
                continue
            metrics = run_data[metric_name]
            metrics_iterator = iter(metrics)
            _metric_steps = (d[xaxis] for d in metrics)
            for step in _all_steps:
                if step not in _metric_steps:
                    _result_dict[metric_name][step, run_label] = None
                else:
                    next_item = next(metrics_iterator)
                    _result_dict[metric_name][step, run_label] = next_item.get("value")

    if parse_to == "dataframe":
        return pd.DataFrame(
            _result_dict,
            index=pd.MultiIndex.from_product(
                [_all_steps, run_labels], names=(xaxis, "run")
            ),
        )
    if parse_to == "dict":
        return _result_dict

    _out_msg: str = f"Unrecognised parse format '{parse_to}'"
    raise ValueError(_out_msg)


def to_dataframe(
    data: list[dict[str, list[str] | dict[str, object]]],
) -> pd.DataFrame:
    """Convert runs to dataframe."""
    _metadata: list[str] = []
    _system_columns: list[str] = []
    _columns: dict[str, list[str | float | None]] = {
        "name": [],
        "status": [],
        "folder": [],
        "created": [],
        "started": [],
        "ended": [],
    }

    for run in data:
        _meta: list[str] = typing.cast("list[str]", run.get("metadata", []))
        _system: dict[str, dict[str, str] | str] = typing.cast(
            "dict[str, dict[str, str] | str]", run.get("system", {}) or {}
        )
        for item in _meta:
            if item not in _metadata:
                _metadata.append(item)
        for item, value in _system.items():
            if isinstance(value, dict):
                _system_columns += [
                    col_name
                    for sub_item in value
                    if (col_name := f"system.{item}.{sub_item}") not in _system_columns
                ]
            elif f"system.{item}" not in _system_columns:
                _system_columns.append(f"system.{item}")

    _columns |= {f"metadata.{column}": [] for column in _metadata} | {
        column: [] for column in _system_columns
    }
    for run in data:
        _run_info: Mapping[str, str] = flatdict.FlatDict(run, delimiter=".")
        for column, value_ in _columns.items():
            try:
                _column_val = typing.cast("str", _run_info.get(column))
                value_.append(_column_val)
            except TypeError:
                value_.append(None)

    return pd.DataFrame(data=_columns)


def metric_time_series_to_dataframe(
    data: list[dict[str, float]],
    xaxis: typing.Literal["step", "time", "timestamp"],
    name: str | None = None,
) -> DataFrame:
    """Convert a single metric value set from a run into a dataframe.

    Parameters
    ----------
    data : list[dict[str, float]]
        time series data from Simvue server for a single metric and run
    xaxis : Literal["step", "time", "timestamp"]
        the x-axis type
            * step - enumeration.
            * time - time in seconds.
            * timestamp - time stamp.
    name : str | None, optional
        if provided, an alternative name for the 'values' column, by default None

    Returns
    -------
    DataFrame
        a pd DataFrame containing values for the metric and run at each
    """
    _df_dict: dict[str, list[float]] = {
        xaxis: [v[xaxis] for v in data],
        name or "value": [v["value"] for v in data],
    }

    return pd.DataFrame(_df_dict)
