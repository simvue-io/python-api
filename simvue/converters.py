"""
Converter Functions
===================

Contains functions for converting objects retrieved from the server between
data types including creation of DataFrames for metrics
"""

import typing
import flatdict

if typing.TYPE_CHECKING:
    from pandas import DataFrame


def to_dataframe(data: list[dict[str, typing.Any]]) -> "DataFrame":
    """Convert runs to a Pandas DataFrame

    Requires Pandas to be installed

    Parameters
    ----------
    data : list[dict[str, typing.Any]]
        data retrieved from a Simvue run for conversion

    Returns
    -------
    DataFrame
        A Pandas data frame
    """
    import pandas as pd

    columns: dict[str, list[typing.Union[int, float, str, None]]] = {}

    for i, run in enumerate(data):
        for column, value in flatdict.FlatDict(run, delimiter=".").items():
            # If the column does not exist create a new one as a list of None
            # these will be filled if present for a run else left as None
            if not columns.get(column):
                columns[column] = [None] * len(data)

            columns[column][i] = value

    return pd.DataFrame(data=columns)


def metric_to_dataframe(
    data: list[list[typing.Union[int, float]]],
    step_axis_label: str,
    name: str
) -> "DataFrame":
    """
    Convert single to dataframe
    """
    import pandas as pd

    columns: dict[str, list[typing.Union[int, float, str]]] = {
        step_axis_label: [i[0] for i in data],
        name: [i[1] for i in data],
    }
    return pd.DataFrame(data=columns)


def metric_set_dataframe(
    data: dict[str, dict[str, list[dict[str, typing.Union[int, float]]]]],
    step_axis_label: str,
) -> "DataFrame":
    """
    Convert metrics to dataframe
    """
    import pandas as pd

    _df_dict: dict[str, list[typing.Union[int, float, str]]] = {
        "run": [],
        step_axis_label: []
    }

    for name, run in data.items():
        for label, metric_steps in run.items():
            if label not in _df_dict:
                _df_dict[label] = []
            _df_dict["run"] = [name] * len(metric_steps)
            _df_dict[step_axis_label] = [i["step"] for i in metric_steps]
            _df_dict[label] += [i["value"] for i in metric_steps]

    _df = pd.DataFrame(_df_dict)
    _df.set_index(["run", "step"], inplace=True)
    return _df
