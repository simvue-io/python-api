import pytest
import logging
from simvue.run import Run
from conftest import RunTestInfo


@pytest.mark.unit
def test_run_init_folder_fail(create_a_run: RunTestInfo) -> None:
    """
    Check that run.init throws an exception if folder input is not specified correctly
    """

    x1_lower = 2
    x1_upper = 6

    run = Run(mode='offline')
    run.config(suppress_errors=False)

    with pytest.raises(RuntimeError) as exc_info:
        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper}, tags=[1,2,3], folder='test_folder',
                description="A test to validate folder input passed into run.init"
        )

    assert exc_info.match(r"string does not match regex")


@pytest.mark.unit
def test_run_init_metadata_fail(create_a_run: RunTestInfo) -> None:
    """
    Check that run.init throws an exception if tuples are passed into metadata dictionary
    """

    x1_lower = 2,
    x1_upper = 6,

    run = Run(mode='offline')
    run.config(suppress_errors=False)

    with pytest.raises(RuntimeError) as exc_info:
        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper},
                description="A test to validate inputs passed into metadata dictionary"
        )

    assert exc_info.match(r"value is not a valid integer")


@pytest.mark.unit
def test_run_init_tags_fail(create_a_run: RunTestInfo) -> None:
    """
    Check that run.init throws an exception if tags are not a list
    """
    x1_lower = 2
    x1_upper = 6

    run = Run(mode='offline')
    run.config(suppress_errors=False)

    with pytest.raises(RuntimeError) as exc_info:
        run.init(metadata={'dataset.x1_lower': x1_lower, 'dataset.x1_upper': x1_upper}, tags=1,
                description="A test to validate tag inputs passed into run.init",
        )

    assert exc_info.match(r"value is not a valid list")


@pytest.mark.unit
def test_suppress_errors_false() -> None:
    """
    Check that exceptions are thrown if suppress_errors disabled
    """
    run = Run()

    with pytest.raises(RuntimeError, match="disable_resources_metrics must be boolean"):
        run.config(
            suppress_errors=False,
            disable_resources_metrics=123,
            )


@pytest.mark.unit
def test_suppress_errors_true(caplog) -> None:
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


@pytest.mark.unit
def test_suppress_errors_default(caplog):
    """
    Check that by default no exceptions are thrown and messages are added to log
    """
    run = Run()

    run.config(
        disable_resources_metrics=123,
    )
    
    caplog.set_level(logging.ERROR)
    
    assert "disable_resources_metrics must be boolean" in caplog.text


@pytest.mark.unit
@pytest.mark.parametrize(
    "func,args,expect", [
        ("init", (), None),
        ("add_process", ("",), None),
        ("config", (), False),
        ("update_metadata", ({},), False),
        ("update_tags", ([],), False),
        ("log_event", ("",), False),
        ("log_metrics", ({},), False),
        ("save", ("", ""), False),
        ("save_directory", ("", ""), False),
        ("save_all", ([], ""), False),
        ("close", (), {}),
        ("set_folder_details", ("",), False),
        ("add_alerts", (), False),
        ("add_alert", ("",), False),
        ("log_alert", ("", ""), False)
    ],
)
def test_dormant_after_suppress(func, args, expect) -> None:
    """
    Check class methods return defaults if error raised
    """
    run = Run()

    run.config(suppress_errors=True)
    run.config(disable_resources_metrics=123)

    assert (_got := getattr(run, func)(*args)) == expect, \
    f"Assertion failed for '{func}': {_got} != {expect}"