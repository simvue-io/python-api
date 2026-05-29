import tempfile
import pytest
import click.testing
import pathlib

from simvue.bin.sender import sender_cli
from simvue.run import Run

from conftest import setup_test_run

@pytest.mark.cli
def test_sender_command(request, monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", tempd)
        with Run(mode="offline") as run:
            _test_run_data = setup_test_run(run, temp_dir=pathlib.Path(tempd), create_objects=True, request=request)
        _runner = click.testing.CliRunner()
        _result = _runner.invoke(
            sender_cli,
            [
                "-i",
                tempd
            ],
            catch_exceptions=False
        )
        assert _result.exit_code == 0, _result.output

