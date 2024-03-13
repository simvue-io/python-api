from simvue import Run
import pytest
import logging

def test_suppress_errors_false():
    """
    Check that exceptions are thrown if suppress_errors disabled
    """
    run = Run()

    with pytest.raises(RuntimeError, match="disable_resources_metrics must be boolean"):
        run.config(
            suppress_errors=False,
            disable_resources_metrics=123,
            )
        
def test_suppress_errors_true(caplog):
    """
    Check that no exceptions are thrown and messages are added to log if suppress_errors enabled
    """
    run = Run()

    run.config(
        suppress_errors=True,
        disable_resources_metrics=123,
        )
    
    caplog.set_level(logging.ERROR)
    
    assert "disable_resources_metrics must be boolean" in caplog.text

def test_suppress_errors_default(caplog):
    """
    Check that by default no exceptions are thrown and messages are added to log
    """
    run = Run()

    run.config(
        suppress_errors=True,
        disable_resources_metrics=123,
        )
    
    caplog.set_level(logging.ERROR)
    
    assert "disable_resources_metrics must be boolean" in caplog.text