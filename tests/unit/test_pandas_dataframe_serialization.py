from simvue.serialization import Serializer, Deserializer
import pandas as pd

def test_pandas_dataframe_serialization():
    """
    Check that a Pandas dataframe can be serialized then deserialized successfully
    """
    data = {'col1': [1, 2], 'col2': [3, 4]}
    df = pd.DataFrame(data=data)

    serialized, mime_type = Serializer().serialize(df)
    df_out = Deserializer().deserialize(serialized, mime_type)

    assert (df.equals(df_out))
