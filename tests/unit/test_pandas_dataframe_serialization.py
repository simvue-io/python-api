import pytest
from simvue.serialization import Serializer, Deserializer

try:
    import pandas as pd
except ImportError:
    pd = None

@pytest.mark.skipif(not pd, reason="Pandas is not installed")
def test_pandas_dataframe_serialization():
    """
    Check that a Pandas dataframe can be serialized then deserialized successfully
    """
    data = {'col1': [1, 2], 'col2': [3, 4]}
    df = pd.DataFrame(data=data)

    serialized, mime_type = Serializer().serialize(df)
    df_out = Deserializer().deserialize(serialized, mime_type)

    assert (df.equals(df_out))
