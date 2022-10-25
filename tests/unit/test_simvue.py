import os
from simvue import client
import pytest

def test_suppress_errors():
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

def test_invalid_url():
    """
    Check invalid URL
    """
    os.environ["SIMVUE_URL"] = "localhost"
    os.environ["SIMVUE_TOKEN"] = "test"

    simv = client.Simvue()

    with pytest.raises(RuntimeError, match=r".*Invalid URL.*"):
        simv.init()

def test_cannot_connect():
    """
    Check unable to connect during init
    """
    os.environ["SIMVUE_URL"] = "http://localhost"
    os.environ["SIMVUE_TOKEN"] = "test"

    simv = client.Simvue()

    with pytest.raises(RuntimeError, match="Failed to establish a new connection"):
        simv.init()
