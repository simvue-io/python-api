from simvue import client
import pytest

def test_supress_errors():
    """
    Check that errors are surpressed
    """

    simv = client.Simvue()

    with pytest.raises(RuntimeError, match="suppress_errors must be boolean"):
        simv.config(suppress_errors=200)

def test_missing_config():
    """
    Check for missing config
    """
    simv = client.Simvue()

    with pytest.raises(RuntimeError, match="Unable to get URL and token from environment variables or config file"):
        simv.init()
