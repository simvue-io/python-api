import io
import pickle
import typing
import enum
import simvue.utilities as sv_util

try:
    import plotly
except ImportError:
    plotly = None

try:
    import numpy
except ImportError:
    numpy = None

try:
    import torch
except ImportError:
    torch = None

try:
    import pandas
except ImportError:
    pandas = None


if typing.TYPE_CHECKING:
    from numpy import ndarray
    from pandas import DataFrame
    from torch import Tensor
    from plotly.graph_objects import Figure, FigureWidget
    from typing_extensions import Buffer


class SimvueMimeType(str, enum.Enum):
    Plotly = "application/vnd.plotly.v1+json"
    Numpy = "application/vnd.simvue.numpy.v1"
    Pandas = "application/vnd.simvue.df.v1"
    Torch = "application/vnd.simvue.torch.v1"
    OctetStream = "application/octet-stream"


def _is_torch_tensor(data: typing.Any) -> bool:
    """
    Check if a dictionary is a PyTorch tensor or state dict
    """
    module_name = data.__class__.__module__
    class_name = data.__class__.__name__

    if isinstance(data, dict):
        return all(_is_torch_tensor(i) for i in data.values())

    return module_name == "torch" and class_name == "Tensor"


def serialize(
    data: typing.Any,
    allow_pickle: bool=False
) -> typing.Callable[[typing.Any], tuple[typing.Optional[typing.Any], typing.Optional[SimvueMimeType]]]:
    """
    Determine which serializer to use
    """
    module_name = data.__class__.__module__
    class_name = data.__class__.__name__

    if module_name == "plotly.graph_objs._figure" and class_name == "Figure":
        return _serialize_plotly_figure(data)
    elif module_name == "matplotlib.figure" and class_name == "Figure":
        return _serialize_matplotlib_figure(data)
    elif module_name == "numpy" and class_name == "ndarray":
        return _serialize_numpy_array(data)
    elif module_name == "pandas.core.frame" and class_name == "DataFrame":
        return _serialize_dataframe(data)
    elif _is_torch_tensor(data):
        return _serialize_torch_tensor(data)
    elif allow_pickle:
        return _serialize_pickle(data)
    return None, None


@sv_util.check_extra("plot")
def _serialize_plotly_figure(
    data,
) -> typing.Union[
        tuple[typing.Union[str, typing.Any, None], SimvueMimeType],
        tuple[None, None]
    ]:
    data = plotly.io.to_json(data, "json")
    return data, SimvueMimeType.Plotly


@sv_util.check_extra("plot")
def _serialize_matplotlib_figure(
    data,
) -> typing.Union[
        tuple[typing.Union[str, typing.Any, None], SimvueMimeType],
        tuple[None, None]
    ]:
    data = plotly.io.to_json(plotly.tools.mpl_to_plotly(data), "json")
    return data, SimvueMimeType.Plotly


@sv_util.check_extra("dataset")
def _serialize_numpy_array(
    data: "ndarray",
) -> typing.Union[tuple[bytes, SimvueMimeType], tuple[None, None]]:
    mfile = io.BytesIO()
    numpy.save(mfile, data, allow_pickle=False)
    mfile.seek(0)
    data = mfile.read()
    return data, SimvueMimeType.Numpy


@sv_util.check_extra("dataset")
def _serialize_dataframe(data: "DataFrame") -> tuple[bytes, SimvueMimeType]:
    mfile = io.BytesIO()
    data.to_csv(mfile)
    mfile.seek(0)
    bytes_data = mfile.read()
    return bytes_data, SimvueMimeType.Pandas


@sv_util.check_extra("torch")
def _serialize_torch_tensor(
    data: "Tensor",
) -> typing.Union[tuple[bytes, SimvueMimeType], tuple[None, None]]:
    mfile = io.BytesIO()
    torch.save(data, mfile)
    mfile.seek(0)
    bytes_data = mfile.read()
    return bytes_data, SimvueMimeType.Torch


def _serialize_pickle(data: typing.Any) -> tuple[bytes, SimvueMimeType]:
    bytes_data = pickle.dumps(data)
    return bytes_data, SimvueMimeType.OctetStream


def deserialize(
    data: typing.Any,
    mimetype: SimvueMimeType,
    allow_pickle: bool=False
) -> typing.Union[
        "Figure",
        "FigureWidget",
        "DataFrame",
        "ndarray",
        "Tensor", 
        typing.Any,
        None
    ]:
    """
    Deserialize the given data
    """
    if mimetype == SimvueMimeType.Plotly:
        return _deserialize_plot_figure(data)
    elif mimetype == SimvueMimeType.Numpy:
        return _deserialize_numpy_array(data)
    elif mimetype == SimvueMimeType.Pandas:
        return _deserialize_dataframe(data)
    elif mimetype == SimvueMimeType.Torch:
        return _deserialize_torch_tensor(data)
    elif mimetype == SimvueMimeType.OctetStream and allow_pickle:
        return _deserialize_pickle(data)
    return None


@sv_util.check_extra("plot")
def _deserialize_plot_figure(
    data: typing.Any,
) -> typing.Union["Figure", "FigureWidget", None]:
    data = plotly.io.from_json(data)
    return data


@sv_util.check_extra("dataset")
def _deserialize_numpy_array(data: "Buffer") -> typing.Union["ndarray", None]:
    mfile = io.BytesIO(data)
    mfile.seek(0)
    data: "ndarray" = numpy.load(mfile, allow_pickle=False)
    return data


@sv_util.check_extra("dataset")
def _deserialize_dataframe(data: "Buffer") -> typing.Union["DataFrame", None]:
    mfile = io.BytesIO(data)
    mfile.seek(0)
    data = pandas.read_csv(mfile, index_col=0)
    return data


@sv_util.check_extra("torch")
def _deserialize_torch_tensor(data: "Buffer") -> typing.Union["Tensor", None]:
    try:
        import torch
    except ImportError:
        torch = None
        return None

    mfile = io.BytesIO(data)
    mfile.seek(0)
    data = torch.load(mfile)
    return data


def _deserialize_pickle(data: "Buffer") -> typing.Union[typing.Any, None]:
    data = pickle.loads(data)
    return data
