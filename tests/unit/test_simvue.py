import os
from simvue import Run
from simvue.serialization import Serializer, Deserializer
import pytest
import numpy as np
import torch
import plotly
import matplotlib.pyplot as plt

def test_suppress_errors():
    """
    Check that errors are surpressed
    """
    run = Run()

    with pytest.raises(RuntimeError, match="suppress_errors must be boolean"):
        run.config(suppress_errors=200)

def test_run_init_metadata():
    """
    Check that run.init throws an exception if tuples are passed into metadata dictionary
    """
    os.environ["SIMVUE_TOKEN"] = "test"
    os.environ["SIMVUE_URL"] = "https://simvue.io"

    x1_lower = 2,
    x1_upper = 6,

    run = Run(mode='offline')

    with pytest.raises(RuntimeError) as exc_info:      
        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper},
                description="A test to validate inputs passed into metadata dictionary"
        )

    assert exc_info.match(r"value is not a valid integer")

def test_run_init_tags():
    """
    Check that run.init throws an exception if tags are not a list
    """
    os.environ["SIMVUE_TOKEN"] = "test"
    os.environ["SIMVUE_URL"] = "https://simvue.io"

    x1_lower = 2
    x1_upper = 6

    run = Run(mode='offline')

    with pytest.raises(RuntimeError) as exc_info:      
        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper}, tags=1,
                description="A test to validate tag inputs passed into run.init"
        )

    assert exc_info.match(r"value is not a valid list")      

def test_run_init_folder():
    """
    Check that run.init throws an exception if folder input is not specified correctly
    """
    os.environ["SIMVUE_TOKEN"] = "test"
    os.environ["SIMVUE_URL"] = "https://simvue.io"

    x1_lower = 2
    x1_upper = 6

    run = Run(mode='offline')

    with pytest.raises(RuntimeError) as exc_info:      
        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper}, tags=[1,2,3], folder='test_folder',
                description="A test to validate folder input passed into run.init"
        )

    assert exc_info.match(r"string does not match regex")         

def test_numpy_array_mime_type():
    """
    Check that the mimetype for numpy arrays is correct
    """
    array = np.array([1, 2, 3, 4, 5])
    _, mime_type = Serializer().serialize(array)

    assert (mime_type == 'application/vnd.simvue.numpy.v1')

def test_pytorch_tensor_mime_type():
    """
    Check that a PyTorch tensor has the correct mime-type
    """
    torch.manual_seed(1724)
    array = torch.rand(2, 3)
    _, mime_type = Serializer().serialize(array)

    assert (mime_type == 'application/vnd.simvue.torch.v1')

def test_matplotlib_figure_mime_type():
    """
    Check that a matplotlib figure has the correct mime-type
    """
    plt.plot([1, 2, 3, 4])
    figure = plt.gcf()

    _, mime_type = Serializer().serialize(figure)

    assert (mime_type == 'application/vnd.plotly.v1+json')

def test_plotly_figure_mime_type():
    """
    Check that a plotly figure has the correct mime-type
    """
    plt.plot([1, 2, 3, 4])
    figure = plt.gcf()
    plotly_figure = plotly.tools.mpl_to_plotly(figure)
    
    _, mime_type = Serializer().serialize(plotly_figure)
    
    assert (mime_type == 'application/vnd.plotly.v1+json')

def test_numpy_array_serialization():
    """
    Check that a numpy array can be serialized then deserialized successfully
    """
    array = np.array([1, 2, 3, 4, 5])

    serialized, mime_type = Serializer().serialize(array)
    array_out = Deserializer().deserialize(serialized, mime_type)

    assert (array == array_out).all()

def test_pytorch_tensor_serialization():
    """
    Check that a PyTorch tensor can be serialized then deserialized successfully
    """
    torch.manual_seed(1724)
    array = torch.rand(2, 3)

    serialized, mime_type = Serializer().serialize(array)
    array_out = Deserializer().deserialize(serialized, mime_type)

    assert (array == array_out).all()

def test_pickle_serialization():
    """
    Check that a dictionary can be serialized then deserialized successfully
    """
    data = {'a': 1.0, 'b': 'test'}

    serialized, mime_type = Serializer().serialize(data, allow_pickle=True)
    data_out = Deserializer().deserialize(serialized, mime_type, allow_pickle=True)

    assert (data == data_out)
