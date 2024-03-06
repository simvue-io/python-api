import pytest
import random
import typing
import simvue.converters as sv_conv

try:
    import pandas
except ImportError:
    pandas = None


@pytest.mark.converters
@pytest.mark.parametrize(
    "xaxis", ("step", "time", "timestamp"),
)
@pytest.mark.skipif(not pandas, reason="Pandas not installed")
def test_metrics_to_dataframe(xaxis: str) -> None:
    ROWS: int = 100
    COLUMNS: int = 10
    TEST_METRICS: list[list[float]] = [
        [random.random() for _ in range(COLUMNS)]
        for _ in range(ROWS)
    ]
    sv_conv.metric_to_dataframe(
        data=TEST_METRICS,
        step_axis_label=xaxis,
        name="values"
    )

@pytest.mark.unit
@pytest.mark.skipif(not pandas, reason="Pandas not installed")
def test_to_dataframe() -> None:
    """
    Check that runs can be successfully converted to a dataframe
    """
    runs = [{'name': 'test1',
             'status': 'completed',
             'folder': '/',
             'created': '2023-01-01 12:13:14',
             'started': '2023-01-01 12:13:15',
             'ended': '2023-01-01 12:13:18',
             'metadata': {'a1': 1, 'b1': 'two'}},
            {'name': 'test2',
             'status': 'completed',
             'folder': '/',
             'created': '2023-01-01 12:14:14',
             'started': '2023-01-01 12:14:15',
             'ended': '2023-01-01 12:14:18',
             'metadata': {'a2': 1, 'b2': 'two'}}]

    runs_df = sv_conv.to_dataframe(runs)

    _expected = [
        'name',
        'status',
        'folder',
        'created',
        'started',
        'ended',
        'metadata.a1',
        'metadata.b1',
        'metadata.a2',
        'metadata.b2'
    ]

    try:
        assert(runs_df.columns.to_list() == _expected)
    except AssertionError:
        _not_in_result = [i for i in _expected if i not in runs_df.columns.to_list()]
        raise AssertionError(
            f"Dataframe creation failed, missing columns: {_not_in_result}"
        )

    data = runs_df.to_dict('records')
    for run, data_entry in zip(runs, data):
        for key in run:
            # If key is present check else accept None
            assert data_entry.get(key) in (run[key], None)

        for item in run['metadata']:
            index = f"metadata.{item}"
            assert(index in data_entry)
            assert(run['metadata'][item] == data_entry[index])


@pytest.mark.unit
@pytest.mark.skipif(not pandas, reason="Pandas not installed")
def test_metric_to_dataframe() -> None:
    _input: list[list[typing.Union[int, float]]] = [
        (x, y, a, b)
        for x, y, a, b in
        zip(
            list(range(10)),
            list(range(100, 110)),
            ["run_test"] * 10,
            ["other"] * 10
        )
    ]

    sv_conv.metric_to_dataframe(_input, step_axis_label="step", name="test_metric")


def test_metric_set_dataframe() -> None:
    _input = {
        "G3VDT4qHactqrsh6CcyPip": {
            "a": [
            {
                "value": 1.0,
                "step": 0
            },
            {
                "value": 1.2,
                "step": 1
            }
            ],
            "b": [
            {
                "value": 2.0,
                "step": 0
            },
            {
                "value": 2.3,
                "step": 1
            }
            ]
        }
    }
    _df = sv_conv.metric_set_dataframe(_input, step_axis_label="step")
    assert _df.iloc[0].name[0] == "G3VDT4qHactqrsh6CcyPip"
