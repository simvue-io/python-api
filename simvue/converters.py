"""
Converter Functions
===================

Contains functions for converting objects retrieved from the server between
data types including creation of DataFrames for metrics
"""

import typing
import pandas
import flatdict


if typing.TYPE_CHECKING:
    from pandas import DataFrame


def aggregated_metrics_to_dataframe(
    request_response_data: dict[str, list[dict[str, float]]],
    xaxis: str,
    parse_to: typing.Literal["dict", "dataframe"] = "dict",
) -> typing.Union["DataFrame", dict[str, dict[tuple[float, str], float]] | None]:
    """Create data frame for an aggregate of metrics

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
            * dataframe - dataframe (Pandas must be installed).

    Returns
    -------
    DataFrame | dict
        a Pandas dataframe of the metric set or the data as a dictionary
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

    result_dict: dict[str, dict[tuple[float, str], float]] | None = {
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
        _data_frame = pandas.DataFrame(result_dict)
        _data_frame.index.name = xaxis
        return _data_frame
    elif parse_to == "dict":
        return result_dict
    else:
        raise ValueError(f"Unrecognised parse format '{parse_to}'")


def parse_run_set_metrics(
    request_response_data: dict[str, dict[str, list[dict[str, float]]]],
    xaxis: str,
    run_labels: list[str],
    parse_to: typing.Literal["dict", "dataframe"] = "dict",
) -> typing.Union[dict[str, dict[tuple[float, str], float]] | None, "DataFrame"]:
    """Parse JSON response metric data from the server into the specified form

    Creates either a dictionary or a pandas dataframe of the data collected
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
            * dataframe - assembled into dataframe (requires Pandas).

    Returns
    -------
    dict[str, dict[tuple[float, str], float]] | None | DataFrame
        either a dictionary or Pandas DataFrame containing the results

    Raises
    ------
    ValueError
        if an unrecognised parse format is specified
    """
    if not request_response_data:
        return pandas.DataFrame({}) if parse_to == "dataframe" else {}

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
        {key for run_data in request_response_data.values() for key in run_data.keys()}
    )

    # Get the keys from the aggregate which are not the xaxis label
    _first_run = next(iter(request_response_data.values()))
    _first_metric_set = next(iter(_first_run.values()))
    _value_types = next(iter(_first_metric_set)).keys()
    _value_types = list(_value_types)
    _value_types.remove(xaxis)

    result_dict: dict[str, dict[tuple[float, str], float]] | None = {
        metric_name: {} for metric_name in _all_metrics
    }

    for run_label, run_data in zip(run_labels, request_response_data.values()):
        for metric_name in _all_metrics:
            if metric_name not in run_data:
                for step in _all_steps:
                    result_dict[metric_name][step, run_label] = None
                continue
            metrics = run_data[metric_name]
            metrics_iterator = iter(metrics)
            _metric_steps = (d[xaxis] for d in metrics)
            for step in _all_steps:
                if step not in _metric_steps:
                    result_dict[metric_name][step, run_label] = None
                else:
                    next_item = next(metrics_iterator)
                    result_dict[metric_name][step, run_label] = next_item.get("value")

    if parse_to == "dataframe":
        return pandas.DataFrame(
            result_dict,
            index=pandas.MultiIndex.from_product(
                [_all_steps, run_labels], names=(xaxis, "run")
            ),
        )
    elif parse_to == "dict":
        return result_dict
    else:
        raise ValueError(f"Unrecognised parse format '{parse_to}'")


def to_dataframe(data) -> pandas.DataFrame:
    """
    Convert runs to dataframe
    """

    metadata = []
    system_columns = []
    columns = {
        "name": [],
        "status": [],
        "folder": [],
        "created": [],
        "started": [],
        "ended": [],
    }

    for run in data:
        for item in run.get("metadata", []):
            if item not in metadata:
                metadata.append(item)
        for item, value in (run.get("system", {}) or {}).items():
            if isinstance(value, dict):
                system_columns += [
                    col_name
                    for sub_item in value.keys()
                    if (col_name := f"system.{item}.{sub_item}") not in system_columns
                ]
            elif f"system.{item}" not in system_columns:
                system_columns.append(f"system.{item}")

    columns |= {f"metadata.{column}": [] for column in metadata} | {
        column: [] for column in system_columns
    }
    for run in data:
        run_info = flatdict.FlatDict(run, delimiter=".")
        for column, value_ in columns.items():
            try:
                value_.append(run_info.get(column))
            except TypeError:
                value_.append(None)

    return pandas.DataFrame(data=columns)


def metric_time_series_to_dataframe(
    data: list[dict[str, float]],
    xaxis: typing.Literal["step", "time", "timestamp"],
    name: str | None = None,
) -> "DataFrame":
    """Convert a single metric value set from a run into a dataframe

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
        a Pandas DataFrame containing values for the metric and run at each
    """

    _df_dict: dict[str, list[float]] = {
        xaxis: [v[xaxis] for v in data],
        name or "value": [v["value"] for v in data],
    }

    return pandas.DataFrame(_df_dict)
