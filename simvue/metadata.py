"""
Metadata
========

Contains functions for extracting additional metadata about the current project

"""

import contextlib
import typing
import json
import os
import fnmatch
import toml
import yaml
import logging
import pathlib

from simvue.models import simvue_timestamp

logger = logging.getLogger(__file__)


def git_info(repository: str) -> dict[str, typing.Any]:
    """Retrieves metadata for the target git repository

    This is a passive function which returns an empty dictionary if any
    metadata is missing. Exceptions are raised only if the repository
    does not have the expected form assumed by this retrieval method.

    Parameters
    ----------
    repository : str
        root directory of the git repository

    Returns
    -------
    dict[str, typing.Any]
        metadata for the target repository
    """
    try:
        import git
    except ImportError:
        return {}

    try:
        git_repo = git.Repo(repository, search_parent_directories=True)
        current_commit: git.Commit = git_repo.head.commit
        author_list: set[str] = {
            email
            for commit in git_repo.iter_commits("--all")
            if "noreply" not in (email := (commit.author.email or ""))
            and "[bot]" not in (commit.author.name or "")
        }

        # In the case where the repository is dirty blame should point to the
        # current developer, not the person responsible for the latest commit
        if dirty := git_repo.is_dirty():
            blame = git_repo.config_reader().get_value("user", "email", "unknown")
        else:
            blame = current_commit.committer.email

        ref: str = next(
            (tag.name for tag in git_repo.tags if tag.commit == current_commit),
            current_commit.hexsha,
        )
        return {
            "git": {
                "authors": list(author_list),
                "ref": ref,
                "msg": current_commit.message.strip(),
                "time_stamp": simvue_timestamp(current_commit.committed_datetime),
                "blame": blame,
                "url": git_repo.remote().url,
                "dirty": dirty,
            }
        }
    except (git.InvalidGitRepositoryError, ValueError):
        return {}


def _conda_dependency_parse(dependency: str) -> tuple[str, str] | None:
    """Parse a dependency definition into module-version."""
    if dependency.startswith("::"):
        logger.warning(
            f"Skipping Conda specific channel definition '{dependency}' in Python environment metadata."
        )
        return None
    elif ">=" in dependency:
        module, version = dependency.split(">=")
        logger.warning(
            f"Ignoring '>=' constraint in Python package version, naively storing '{module}=={version}', "
            "for a more accurate record use 'conda env export > environment.yml'"
        )
    elif "~=" in dependency:
        module, version = dependency.split("~=")
        logger.warning(
            f"Ignoring '~=' constraint in Python package version, naively storing '{module}=={version}', "
            "for a more accurate record use 'conda env export > environment.yml'"
        )
    elif dependency.startswith("-e"):
        _, version = dependency.split("-e")
        version = version.strip()
        module = pathlib.Path(version).name
    elif dependency.startswith("file://"):
        _, version = dependency.split("file://")
        module = pathlib.Path(version).stem
    elif dependency.startswith("git+"):
        _, version = dependency.split("git+")
        if "#egg=" in version:
            repo, module = version.split("#egg=")
            module = repo.split("/")[-1].replace(".git", "")
        else:
            module = version.split("/")[-1].replace(".git", "")
    elif "==" not in dependency:
        logger.warning(
            f"Ignoring '{dependency}' in Python environment record as no version constraint specified."
        )
        return None
    else:
        module, version = dependency.split("==")

    return module, version


def _conda_env(environment_file: pathlib.Path) -> dict[str, str]:
    """Parse/interpret a Conda environment file."""
    content = yaml.load(environment_file.open(), Loader=yaml.SafeLoader)
    python_environment: dict[str, str] = {}
    pip_dependencies: list[str] = []
    for dependency in content.get("dependencies", []):
        if isinstance(dependency, dict) and dependency.get("pip"):
            pip_dependencies = dependency["pip"]
            break

    for dependency in pip_dependencies:
        if not (parsed := _conda_dependency_parse(dependency)):
            continue
        module, version = parsed
        python_environment[module.strip().replace("-", "_")] = version.strip()
    return python_environment


def _python_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Python dependencies if lock file is available"""
    python_meta: dict[str, dict] = {}

    if (pyproject_file := pathlib.Path(repository).joinpath("pyproject.toml")).exists():
        content = toml.load(pyproject_file)
        if (poetry_content := content.get("tool", {}).get("poetry", {})).get("name"):
            python_meta["project"] = {
                "name": poetry_content["name"],
                "version": poetry_content["version"],
            }
        elif other_content := content.get("project"):
            python_meta["project"] = {
                "name": other_content["name"],
                "version": other_content["version"],
            }

    if (poetry_lock_file := pathlib.Path(repository).joinpath("poetry.lock")).exists():
        content = toml.load(poetry_lock_file).get("package", {})
        python_meta["environment"] = {
            package["name"]: package["version"] for package in content
        }
    elif (uv_lock_file := pathlib.Path(repository).joinpath("uv.lock")).exists():
        content = toml.load(uv_lock_file).get("package", {})
        python_meta["environment"] = {
            package["name"]: package["version"] for package in content
        }
    # Handle Conda case, albeit naively given the user may or may not have used 'conda env'
    # to dump their exact dependency versions
    elif (
        environment_file := pathlib.Path(repository).joinpath("environment.yml")
    ).exists():
        python_meta["environment"] = _conda_env(environment_file)
    else:
        with contextlib.suppress((KeyError, ImportError)):
            from pip._internal.operations.freeze import freeze

            # Conda supports having file names with @ as entries
            # in the requirements.txt file as opposed to ==
            python_meta["environment"] = {}

            for line in freeze(local_only=True):
                if line.startswith("-e"):
                    python_meta["environment"]["local_install"] = line.split(" ")[-1]
                    continue
                if "@" in line:
                    entry = line.split("@")
                    python_meta["environment"][entry[0].strip()] = entry[-1].strip()
                elif "==" in line:
                    entry = line.split("==")
                    python_meta["environment"][entry[0].strip()] = entry[-1].strip()

    return python_meta


def _rust_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Rust dependencies if lock file available"""
    rust_meta: dict[str, dict] = {}

    if (cargo_file := pathlib.Path(repository).joinpath("Cargo.toml")).exists():
        content = toml.load(cargo_file).get("package", {})
        if version := content.get("version"):
            rust_meta.setdefault("project", {})["version"] = version

        if name := content.get("name"):
            rust_meta.setdefault("project", {})["name"] = name

    if not (cargo_lock := pathlib.Path(repository).joinpath("Cargo.lock")).exists():
        return rust_meta

    cargo_dat = toml.load(cargo_lock)
    rust_meta["environment"] = {
        dependency["name"]: dependency["version"]
        for dependency in cargo_dat.get("package", [])
    }

    return rust_meta


def _julia_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Julia dependencies if a project file is available"""
    julia_meta: dict[str, dict] = {}
    if (project_file := pathlib.Path(repository).joinpath("Project.toml")).exists():
        content = toml.load(project_file)
        julia_meta["project"] = {
            key: value for key, value in content.items() if not isinstance(value, dict)
        }
        julia_meta["environment"] = {
            key: value for key, value in content.get("compat", {}).items()
        }
    return julia_meta


def _node_js_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    js_meta: dict[str, dict] = {}
    if (
        project_file := pathlib.Path(repository).joinpath("package-lock.json")
    ).exists():
        content = json.load(project_file.open())
        if (lfv := content["lockfileVersion"]) not in (1, 2, 3):
            logger.warning(
                f"Unsupported package-lock.json lockfileVersion {lfv}, ignoring JS project metadata"
            )
            return {}

        js_meta["project"] = {
            key: value for key, value in content.items() if key in ("name", "version")
        }
        js_meta["environment"] = {
            key.replace("@", ""): value["version"]
            for key, value in content.get(
                "packages" if lfv in (2, 3) else "dependencies", {}
            ).items()
            if key and not value.get("dev", True)
        }
    return js_meta


def _environment_variables(glob_exprs: list[str]) -> dict[str, str]:
    """Retrieve values for environment variables."""
    _env_vars: list[str] = list(os.environ.keys())
    _metadata: dict[str, str] = {}

    for pattern in glob_exprs:
        for key in fnmatch.filter(_env_vars, pattern):
            _metadata[key] = os.environ[key]

    return _metadata


def environment(
    repository: pathlib.Path = pathlib.Path.cwd(),
    env_var_glob_exprs: set[str] | None = None,
) -> dict[str, typing.Any]:
    """Retrieve environment metadata"""
    _environment_meta = {}
    if _python_meta := _python_env(repository):
        _environment_meta["python"] = _python_meta
    if _rust_meta := _rust_env(repository):
        _environment_meta["rust"] = _rust_meta
    if _julia_meta := _julia_env(repository):
        _environment_meta["julia"] = _julia_meta
    if _js_meta := _node_js_env(repository):
        _environment_meta["javascript"] = _js_meta
    if env_var_glob_exprs:
        _environment_meta["shell"] = _environment_variables(env_var_glob_exprs)
    return _environment_meta
