from simvue.serialization import serialize_object, deserialize_data
import pandas as pd
import pytest

try:
    import pandas as pd
except ImportError:
    pd = None

@pytest.mark.local
@pytest.mark.skipif(not pd, reason="Pandas is not installed")
def test_pandas_dataframe_serialization() -> None:
    """
    Check that a Pandas dataframe can be serialized then deserialized successfully
    """
    data = {'col1': [1, 2], 'col2': [3, 4]}
    df = pd.DataFrame(data=data)

    serialized, mime_type = serialize_object(df, False)
    df_out = deserialize_data(serialized, mime_type, False)

    assert (df.equals(df_out))
