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
    "backend", ("poetry", "uv", "conda", None)
)
def test_python_env(backend: str | None) -> None:
    if backend == "poetry":
        metadata = sv_meta._python_env(pathlib.Path(__file__).parents[1].joinpath("example_data", "python_poetry"))
        assert metadata["project"]["name"] == "example-repo"
    elif backend == "uv":
        metadata = sv_meta._python_env(pathlib.Path(__file__).parents[1].joinpath("example_data", "python_uv"))
        assert metadata["project"]["name"] == "example-repo"
    elif backend == "conda":
        metadata = sv_meta._python_env(pathlib.Path(__file__).parents[1].joinpath("example_data", "python_conda"))
        assert metadata["environment"]["requests"]
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
