import typing

if typing.TYPE_CHECKING:
    from pandas import DataFrame


def to_dataframe(data: list[dict[str, typing.Any]]) -> "DataFrame":
    """
    Convert runs to dataframe
    """
    import pandas as pd

    metadata: list[dict[str, typing.Any]] = []
    columns: dict[str, list[typing.Any]] = {
        "name": [],
        "status": [],
        "folder": [],
        "created": [],
        "started": [],
        "ended": []
    }

    for run in data:
        metadata += [
            item for item in run.get("metadata", [])
            if item not in metadata
        ]

        for label, column in columns.items():
            column.append(run.get(label))

        _system_info: dict[str, dict | str | int | float] = run.get("system", {})
 
        for section, values in _system_info.items():
            if section in ("cpu", "gpu", "platform"):
                for label, item in values.items():
                    _key = f"system.{section}.{label}"
                    columns[_key] = columns.get(_key, []).append(item)
            else:
                _key = f"system.{section}"
                columns[_key] = columns.get(_key, []).append(values)

        for label in metadata:
            _item = run.get("metadata", {}).get(label)
            _key = f"metadata{section}.{label}"
            columns[_key] = columns.get(_key, []).append(_item)

    return pd.DataFrame(data=columns)


def metrics_to_dataframe(data: list[list[str]], xaxis: str, name: str | None=None):
    """
    Convert metrics to dataframe
    """
    import pandas as pd

    if name:
        columns: dict[str, list[str | int | float]] = {
            xaxis: [],
            name: []
        }
        for item in data:
            columns[xaxis].append(item[0])
            columns[name].append(item[1])

        return pd.DataFrame(data=columns)

    runs = []
    metrics = []

    for item in data:
        if item[2] not in runs:
            runs.append(item[2])
        if item[3] not in metrics:
            metrics.append(item[3])

    headers = pd.MultiIndex.from_product([runs, metrics, [xaxis, "value"]], names=["run", "metric", "column"])

    newdata = {}
    for row in data:
        if row[2] not in newdata:
            newdata[row[2]] = {}
        if row[3] not in newdata[row[2]]:
            newdata[row[2]][row[3]] = []

        newdata[row[2]][row[3]].append([row[0], row[1]])

    max_rows = 0
    for run in newdata:
        for metric in newdata[run]:
            if len(newdata[run][metric]) > max_rows:
                max_rows = len(newdata[run][metric])

    results = []
    for count in range (0, max_rows):
        line = []
        for run in newdata:
            for metric in newdata[run]:
                if count < len(newdata[run][metric]):
                    line.append(newdata[run][metric][count][0])
                    line.append(newdata[run][metric][count][1])
                else:
                    line.append(None)
                    line.append(None)
        results.append(line)

    df = pd.DataFrame(data=results, columns=headers)
    return df
