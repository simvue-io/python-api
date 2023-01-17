from io import BytesIO
import os
import pickle
import numpy as np
import pandas as pd
import plotly

class Serializer:
    def serialize(self, data, allow_pickle=False):
        serializer = get_serializer(data, allow_pickle)
        if serializer:
            return serializer(data)
        return None, None

def get_serializer(data, allow_pickle):
    """
    Determine which serializer to use
    """
    module_name = data.__class__.__module__
    class_name = data.__class__.__name__

    if module_name == 'plotly.graph_objs._figure' and class_name == 'Figure':
        return _serialize_plotly_figure
    elif module_name == 'matplotlib.figure' and class_name == 'Figure':
        return _serialize_matplotlib_figure
    elif module_name == 'numpy' and class_name == 'ndarray':
        return _serialize_numpy_array
    elif module_name == 'pandas.core.frame' and class_name == 'DataFrame':
        return _serialize_dataframe
    elif allow_pickle:
        return _serialize_pickle
    return None

def _serialize_plotly_figure(data):
    mimetype = 'application/vnd.plotly.v1+json'
    data = plotly.io.to_json(data, 'json')
    return data, mimetype

def _serialize_matplotlib_figure(data):
    mimetype = 'application/vnd.plotly.v1+json'
    data = plotly.io.to_json(plotly.tools.mpl_to_plotly(data), 'json')
    return data, mimetype

def _serialize_numpy_array(data):
    mimetype = 'application/vnd.simvue.numpy.v1'
    mfile = BytesIO()
    np.save(mfile, data, allow_pickle=False)
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype

def _serialize_dataframe(data):
    mimetype = 'application/vnd.simvue.df.v1'
    mfile = BytesIO()
    data.to_csv(mfile)
    mfile.seek(0)
    data = mfile.read()
    return data, mimetype

def _serialize_pickle(data):
    mimetype = 'application/octet-stream'
    data = pickle.dumps(data)
    return data

class Deserializer:
    def deserialize(self, data, mimetype, allow_pickle=False):
        deserializer = get_deserializer(data, mimetype, allow_pickle)
        if deserializer:
            return deserializer(data)
        return None

def get_deserializer(data, mimetype, allow_pickle):
    """
    Determine which deserializer to use
    """
    if mimetype == 'application/vnd.plotly.v1+json':
        return _deserialize_plotly_figure
    elif mimetype == 'application/vnd.plotly.v1+json':
        return _deserialize_matplotlib_figure
    elif mimetype == 'application/vnd.simvue.numpy.v1':
        return _deserialize_numpy_array
    elif mimetype == 'application/vnd.simvue.df.v1':
        return _deserialize_dataframe
    elif mimetype == 'application/octet-stream' and allow_pickle:
        return _deserialize_pickle
    return None

def _deserialize_plotly_figure(data):
    data = plotly.io.from_json(data)
    return data

def _deserialize_matplotlib_figure(data):
    data = plotly.io.from_json(data)
    return data

def _deserialize_numpy_array(data):
    mfile = BytesIO(data)
    mfile.seek(0)
    data = np.load(mfile, allow_pickle=False)
    return data

def _deserialize_dataframe(data):
    mfile = BytesIO(data)
    mfile.seek(0)
    data = pd.read_csv(mfile)
    return data

def _deserialize_pickle(data):
    data = pickle.loads(data)
    return data
