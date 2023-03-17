import os
from simvue import Run
import pytest

def test_run_init_folder():
    """
    Check that run.init throws an exception if folder input is not specified correctly
    """
    os.environ["SIMVUE_TOKEN"] = "test"
    os.environ["SIMVUE_URL"] = "https://simvue.io"

    x1_lower = 2
    x1_upper = 6

    run = Run(mode='offline')

    with pytest.raises(RuntimeError) as exc_info:
        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper}, tags=[1,2,3], folder='test_folder',
                description="A test to validate folder input passed into run.init"
        )

    assert exc_info.match(r"string does not match regex")
