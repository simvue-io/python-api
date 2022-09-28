from simvue import client
import pytest

def test_supress_errors():
    """
    Check that errors are surpressed
    """

    simv = client.Simvue()

    with pytest.raises(RuntimeError, match="value must be boolean"):
        simv.config(suppress_errors=200)
