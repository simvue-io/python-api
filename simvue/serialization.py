"""
Object Serialization
====================

Contains serializers for storage of objects on the Simvue server
"""

import contextlib
import typing
import pickle
import pandas
import json
import numpy

from io import BytesIO

if typing.TYPE_CHECKING:
    from pandas import DataFrame
    from plotly.graph_objects import Figure
    from torch import Tensor
    from typing_extensions import Buffer
    from .types import DeserializedContent

from .utilities import check_extra


def _is_torch_tensor(data: typing.Any) -> bool:
    """
    Check if value is a PyTorch tensor or state dict
    """
    module_name = data.__class__.__module__
    class_name = data.__class__.__name__

    if module_name == "collections" and class_name == "OrderedDict":
        valid = True
        for item in data:
            module_name = data[item].__class__.__module__
            class_name = data[item].__class__.__name__
            if module_name != "torch" or class_name != "Tensor":
                valid = False
        if valid:
            return True
    elif module_name == "torch" and class_name == "Tensor":
        return True

    return False


def serialize_object(data: typing.Any, allow_pickle: bool) -> tuple[str, str] | None:
    """Determine which serializer to use for the given object

    Parameters
    ----------
    data : typing.Any
        object to serialize
    allow_pickle : bool
        whether pickling is allowed

    Returns
    -------
    Callable[[typing.Any], tuple[str, str]]
        the serializer to use
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
    elif module_name == "builtins" and class_name == "module" and not allow_pickle:
        with contextlib.suppress(ImportError):
            import matplotlib.pyplot

            if data == matplotlib.pyplot:
                return _serialize_matplotlib(data)
    elif serialized := _serialize_json(data):
        return serialized

    return _serialize_pickle(data) if allow_pickle else None


@check_extra("plot")
def _serialize_plotly_figure(data: typing.Any) -> tuple[str, str]:
    try:
        import plotly
    except ImportError:
        return None
    mimetype = "application/vnd.plotly.v1+json"
    data = plotly.io.to_json(data, engine="json")
    mfile = BytesIO()
    mfile.write(data.encode())
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype


@check_extra("plot")
def _serialize_matplotlib(data: typing.Any) -> tuple[str, str] | None:
    try:
        import plotly
    except ImportError:
        return None
    mimetype = "application/vnd.plotly.v1+json"
    data = plotly.io.to_json(plotly.tools.mpl_to_plotly(data.gcf()), engine="json")
    mfile = BytesIO()
    mfile.write(data.encode())
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype


@check_extra("plot")
def _serialize_matplotlib_figure(data: typing.Any) -> tuple[str, str] | None:
    try:
        import plotly
    except ImportError:
        return None
    mimetype = "application/vnd.plotly.v1+json"
    data = plotly.io.to_json(plotly.tools.mpl_to_plotly(data), engine="json")
    mfile = BytesIO()
    mfile.write(data.encode())
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype


def _serialize_numpy_array(data: typing.Any) -> tuple[str, str] | None:
    mimetype = "application/vnd.simvue.numpy.v1"
    mfile = BytesIO()
    numpy.save(mfile, data, allow_pickle=False)
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype


def _serialize_dataframe(data: typing.Any) -> tuple[str, str] | None:
    mimetype = "application/vnd.simvue.df.v1"
    mfile = BytesIO()
    data.to_csv(mfile)
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype


@check_extra("torch")
def _serialize_torch_tensor(data: typing.Any) -> tuple[str, str] | None:
    try:
        import torch
    except ImportError:
        torch = None
        return None

    mimetype = "application/vnd.simvue.torch.v1"
    mfile = BytesIO()
    torch.save(data, mfile)
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype


def _serialize_json(data: typing.Any) -> tuple[str, str] | None:
    mimetype = "application/json"
    try:
        mfile = BytesIO()
        mfile.write(json.dumps(data).encode())
        mfile.seek(0)
        data = mfile.read()
    except (TypeError, json.JSONDecodeError):
        return None
    return data, mimetype


def _serialize_pickle(data: typing.Any) -> tuple[str, str] | None:
    mimetype = "application/octet-stream"
    data = pickle.dumps(data)
    return data, mimetype


def deserialize_data(
    data: "Buffer", mimetype: str, allow_pickle: bool
) -> typing.Optional["DeserializedContent"]:
    """
    Determine which deserializer to use
    """
    if mimetype == "application/vnd.plotly.v1+json":
        return _deserialize_plotly_figure(data)
    elif mimetype == "application/vnd.simvue.numpy.v1":
        return _deserialize_numpy_array(data)
    elif mimetype == "application/vnd.simvue.df.v1":
        return _deserialize_dataframe(data)
    elif mimetype == "application/vnd.simvue.torch.v1":
        return _deserialize_torch_tensor(data)
    elif mimetype == "application/json":
        return _deserialize_json(data)
    elif mimetype == "application/octet-stream" and allow_pickle:
        return _deserialize_pickle(data)
    return None


@check_extra("plot")
def _deserialize_plotly_figure(data: "Buffer") -> typing.Optional["Figure"]:
    try:
        import plotly
    except ImportError:
        return None
    data = plotly.io.from_json(data)
    return data


@check_extra("plot")
def _deserialize_matplotlib_figure(data: "Buffer") -> typing.Optional["Figure"]:
    try:
        import plotly
    except ImportError:
        return None
    data = plotly.io.from_json(data)
    return data


def _deserialize_numpy_array(data: "Buffer") -> typing.Any | None:
    mfile = BytesIO(data)
    mfile.seek(0)
    data = numpy.load(mfile, allow_pickle=False)
    return data


def _deserialize_dataframe(data: "Buffer") -> typing.Optional["DataFrame"]:
    mfile = BytesIO(data)
    mfile.seek(0)
    return pandas.read_csv(mfile, index_col=0)


@check_extra("torch")
def _deserialize_torch_tensor(data: "Buffer") -> typing.Optional["Tensor"]:
    try:
        import torch
    except ImportError:
        torch = None
        return None

    mfile = BytesIO(data)
    mfile.seek(0)
    return torch.load(mfile)


def _deserialize_pickle(data) -> typing.Any | None:
    data = pickle.loads(data)
    return data


def _deserialize_json(data) -> typing.Any | None:
    data = json.loads(data)
    return data
