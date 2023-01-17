from io import BytesIO
import os
import numpy as np
import plotly

class Serializer:
    def serialize(self, data):
        serializer = get_serializer(data)
        return serializer(data)

def get_serializer(data):
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
    else:
        return None, None

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
