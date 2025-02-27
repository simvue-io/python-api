from simvue.serialization import serialize_object
import numpy as np
import pytest

@pytest.mark.local
def test_numpy_array_mime_type() -> None:
    """
    Check that the mimetype for numpy arrays is correct
    """
    array = np.array([1, 2, 3, 4, 5])
    _, mime_type = serialize_object(array, False)

    assert (mime_type == 'application/vnd.simvue.numpy.v1')
