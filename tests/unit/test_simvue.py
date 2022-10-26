import os
from simvue import Run
import pytest

def test_suppress_errors():
    """
    Check that errors are surpressed
    """
    run = Run()

    with pytest.raises(RuntimeError, match="suppress_errors must be boolean"):
        run.config(suppress_errors=200)

def test_missing_config():
    """
    Check for missing config
    """
    run = Run()

    with pytest.raises(RuntimeError, match="Unable to get URL and token from environment variables or config file"):
        run.init()

def test_invalid_url():
    """
    Check invalid URL
    """
    os.environ["SIMVUE_URL"] = "localhost"
    os.environ["SIMVUE_TOKEN"] = "test"

    run = Run()

    with pytest.raises(RuntimeError, match=r".*Invalid URL.*"):
        run.init()

def test_cannot_connect():
    """
    Check unable to connect during init
    """
    os.environ["SIMVUE_URL"] = "http://localhost"
    os.environ["SIMVUE_TOKEN"] = "test"

    run = Run()

    with pytest.raises(RuntimeError, match="Failed to establish a new connection"):
        run.init()
