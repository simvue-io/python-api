from simvue.serialization import Serializer, Deserializer
import numpy as np

def test_numpy_array_mime_type():
    """
    Check that the mimetype for numpy arrays is correct
    """
    array = np.array([1, 2, 3, 4, 5])
    _, mime_type = Serializer().serialize(array)

    assert (mime_type == 'application/vnd.simvue.numpy.v1')
