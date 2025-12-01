import tempfile
from typing import Any
import pytest
import click.testing
import os

from simvue.bin.sender import run
from simvue.run import Run

from conftest import create_test_run_offline, setup_test_run

@pytest.mark.cli
def test_sender_command(request, monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", tempd)
        _run = Run(mode="offline")
        setup_test_run(_run, temp_dir=tempd, create_objects=True, request=request)
        _run.close()
        _runner = click.testing.CliRunner()
        _result = _runner.invoke(
            run,
            [
                "-i",
                tempd
            ],
            catch_exceptions=False
        )
        assert _result.exit_code == 0, _result.output

