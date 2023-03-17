import pandas as pd
from simvue.serialization import Serializer, Deserializer

def test_pickle_serialization():
    """
    Check that a dictionary can be serialized then deserialized successfully
    """
    data = {'a': 1.0, 'b': 'test'}

    serialized, mime_type = Serializer().serialize(data, allow_pickle=True)
    data_out = Deserializer().deserialize(serialized, mime_type, allow_pickle=True)

    assert (data == data_out)
