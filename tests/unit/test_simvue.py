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

def test_run_init_metadata():
    """
    Check that run.init throws an exception if tuples are passed into metadata dictionary
    """
    os.environ["SIMVUE_TOKEN"] = "test"
    os.environ["SIMVUE_URL"] = "https://simvue.io"

    x1_lower = 2,
    x1_upper = 6,

    run = Run(mode='offline')

    with pytest.raises(RuntimeError) as exc_info:      

        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper},
                description="A test to validate inputs passed into metadata dictionary"
        )

    assert exc_info.match(r"value is not a valid integer")

    with pytest.raises(RuntimeError) as exc_info:      

        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper}, tags=1,
                description="A test to validate inputs passed into folder"
        )

    assert exc_info.match(r"value is not a valid integer")    

def test_run_init_tags():
    """
    Check that run.init throws an exception if tags are not a list
    """
    os.environ["SIMVUE_TOKEN"] = "test"
    os.environ["SIMVUE_URL"] = "https://simvue.io"

    x1_lower = 2
    x1_upper = 6

    run = Run(mode='offline')

    with pytest.raises(RuntimeError) as exc_info:      

        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper}, tags=1,
                description="A test to validate tag inputs passed into run.init"
        )

    assert exc_info.match(r"value is not a valid list")      

