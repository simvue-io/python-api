import pytest
from simvue.converters import to_dataframe, metric_set_dataframe, metric_to_dataframe
from simvue.serialization import Serializer, Deserializer


try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import plotly
except ImportError:
    plotly = None


try:
    import torch
except ImportError:
    torch = None


@pytest.mark.unit
@pytest.mark.skipif(plt is None, reason="Matplotlib not installed")
def test_matplotlib_figure_mime_type() -> None:
    """
    Check that a matplotlib figure has the correct mime-type
    """
    plt.plot([1, 2, 3, 4])
    figure = plt.gcf()

    _, mime_type = Serializer().serialize(figure)

    assert (mime_type == 'application/vnd.plotly.v1+json')


@pytest.mark.unit
@pytest.mark.skipif(np is None, reason="Numpy not installed")
def test_numpy_array_mime_type() -> None:
    """
    Check that the mimetype for numpy arrays is correct
    """
    array = np.array([1, 2, 3, 4, 5])
    _, mime_type = Serializer().serialize(array)

    assert (mime_type == 'application/vnd.simvue.numpy.v1')


@pytest.mark.unit
@pytest.mark.skipif(pd is None, reason="Pandas not installed")
def test_pandas_dataframe_mimetype() -> None:
    """
    Check that the mime-type of a Pandas dataframe is correct
    """
    data = {'col1': [1, 2], 'col2': [3, 4]}
    df = pd.DataFrame(data=data)

    _, mime_type = Serializer().serialize(df)

    assert (mime_type == 'application/vnd.simvue.df.v1')


@pytest.mark.unit
@pytest.mark.skipif(pd is None, reason="Pandas not installed")
def test_pandas_dataframe_serialization() -> None:
    """
    Check that a Pandas dataframe can be serialized then deserialized successfully
    """
    data = {'col1': [1, 2], 'col2': [3, 4]}
    df = pd.DataFrame(data=data)

    serialized, mime_type = Serializer().serialize(df)
    df_out = Deserializer().deserialize(serialized, mime_type)

    assert (df.equals(df_out))


@pytest.mark.unit
@pytest.mark.skipif(np is None, reason="Numpy not installed")
def test_numpy_array_serialization() -> None:
    """
    Check that a numpy array can be serialized then deserialized successfully
    """
    array = np.array([1, 2, 3, 4, 5])

    serialized, mime_type = Serializer().serialize(array)
    array_out = Deserializer().deserialize(serialized, mime_type)

    assert (array == array_out).all()


@pytest.mark.unit
def test_pickle_serialization():
    """
    Check that a dictionary can be serialized then deserialized successfully
    """
    data = {'a': 1.0, 'b': 'test'}

    serialized, mime_type = Serializer().serialize(data, allow_pickle=True)
    data_out = Deserializer().deserialize(serialized, mime_type, allow_pickle=True)

    assert (data == data_out)


@pytest.mark.unit
@pytest.mark.skipif(plt is None or plotly is None, reason="Plotly not installed")
def test_plotly_figure_mime_type() -> None:
    """
    Check that a plotly figure has the correct mime-type
    """
    plt.plot([1, 2, 3, 4])
    figure = plt.gcf()
    plotly_figure = plotly.tools.mpl_to_plotly(figure)

    _, mime_type = Serializer().serialize(plotly_figure)

    assert (mime_type == 'application/vnd.plotly.v1+json')


@pytest.mark.unit
@pytest.mark.skipif(torch is None, reason="PyTorch not installed")
def test_pytorch_tensor_mime_type():
    """
    Check that a PyTorch tensor has the correct mime-type
    """
    torch.manual_seed(1724)
    array = torch.rand(2, 3)
    _, mime_type = Serializer().serialize(array)

    assert (mime_type == 'application/vnd.simvue.torch.v1')


@pytest.mark.unit
@pytest.mark.skipif(torch is None, reason="PyTorch not installed")
def test_pytorch_tensor_serialization() -> None:
    """
    Check that a PyTorch tensor can be serialized then deserialized successfully
    """
    torch.manual_seed(1724)
    array = torch.rand(2, 3)

    serialized, mime_type = Serializer().serialize(array)
    array_out = Deserializer().deserialize(serialized, mime_type)

    assert (array == array_out).all()


@pytest.mark.unit
@pytest.mark.skipif(pd is None, reason="Pandas not installed")
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

    runs_df = to_dataframe(runs)

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
@pytest.mark.skipif(pd is None, reason="Pandas not installed")
def test_metric_to_dataframe() -> None:
    _input: list[list[int | float]] = [
        (x, y, a, b)
        for x, y, a, b in
        zip(
            list(range(10)),
            list(range(100, 110)),
            ["run_test"] * 10,
            ["other"] * 10
        )
    ]

    metric_to_dataframe(_input, step_axis_label="step", name="test_metric")


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
    _df = metric_set_dataframe(_input, step_axis_label="step")
    assert _df.iloc[0].name[0] == "G3VDT4qHactqrsh6CcyPip"