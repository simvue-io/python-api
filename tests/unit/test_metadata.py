import os
import pytest
import pathlib
import re
import simvue.metadata as sv_meta


@pytest.mark.metadata
@pytest.mark.local
def test_cargo_env() -> None:
    metadata = sv_meta._rust_env(pathlib.Path(__file__).parents[1].joinpath("example_data"))
    assert metadata["environment"]["serde"] == "1.0.123"
    assert metadata["project"]["name"] == "example_project"

@pytest.mark.metadata
@pytest.mark.local
@pytest.mark.parametrize(
    "backend", ("poetry", "uv", None)
)
def test_python_env(backend: str | None) -> None:
    if backend == "poetry":
        metadata = sv_meta._python_env(pathlib.Path(__file__).parents[1].joinpath("example_data", "python_poetry"))
        assert metadata["project"]["name"] == "example-repo"
    elif backend == "uv":
        metadata = sv_meta._python_env(pathlib.Path(__file__).parents[1].joinpath("example_data", "python_uv"))
        assert metadata["project"]["name"] == "example-repo"
    else:
        metadata = sv_meta._python_env(pathlib.Path(__file__).parents[1].joinpath("example_data"))

    assert re.findall(r"\d+\.\d+\.\d+", metadata["environment"]["numpy"])


@pytest.mark.metadata
@pytest.mark.local
def test_julia_env() -> None:
    metadata = sv_meta._julia_env(pathlib.Path(__file__).parents[1].joinpath("example_data"))
    assert metadata["project"]["name"] == "Julia Demo Project"
    assert re.findall(r"\d+\.\d+\.\d+", metadata["environment"]["AbstractDifferentiation"])


@pytest.mark.metadata
@pytest.mark.local
def test_js_env() -> None:
    metadata = sv_meta._node_js_env(pathlib.Path(__file__).parents[1].joinpath("example_data"))
    assert metadata["project"]["name"] == "my-awesome-project"
    assert re.findall(r"\d+\.\d+\.\d+", metadata["environment"]["node_modules/dotenv"])

@pytest.mark.metadata
@pytest.mark.local
def test_environment() -> None:
    metadata = sv_meta.environment(pathlib.Path(__file__).parents[1].joinpath("example_data"))
    assert metadata["python"]["project"]["name"] == "example-repo"
    assert metadata["rust"]["project"]["name"] == "example_project"
    assert metadata["julia"]["project"]["name"] == "Julia Demo Project"
    assert metadata["javascript"]["project"]["name"] == "my-awesome-project"


@pytest.mark.metadata
@pytest.mark.local
def test_slurm_env_var_capture() -> None:
    _slurm_env = {
        "SLURM_CPUS_PER_TASK": "2",
        "SLURM_TASKS_PER_NODE": "1",
        "SLURM_NNODES": "1",
        "SLURM_NTASKS_PER_NODE": "1",
        "SLURM_NTASKS": "1",
        "SLURM_JOB_CPUS_PER_NODE": "2",
        "SLURM_CPUS_ON_NODE": "2",
        "SLURM_JOB_NUM_NODES": "1",
        "SLURM_MEM_PER_NODE": "2000",
        "SLURM_NPROCS": "1",
        "SLURM_TRES_PER_TASK": "cpu:2",
    }
    os.environ.update(_slurm_env)

    sv_meta.metadata = sv_meta.environment(env_var_glob_exprs={"SLURM_*"})
    assert all((key, value) in sv_meta.metadata["shell"].items() for key, value in _slurm_env.items())
