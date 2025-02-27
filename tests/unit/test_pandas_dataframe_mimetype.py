import pandas as pd
from simvue.serialization import serialize_object
import pytest

try:
    import pandas as pd
except ImportError:
    pd = None

@pytest.mark.local
@pytest.mark.skipif(not pd, reason="Pandas is not installed")
def test_pandas_dataframe_mimetype() -> None:
    """
    Check that the mime-type of a Pandas dataframe is correct
    """
    data = {'col1': [1, 2], 'col2': [3, 4]}
    df = pd.DataFrame(data=data)

    _, mime_type = serialize_object(df, False)

    assert (mime_type == 'application/vnd.simvue.df.v1')
