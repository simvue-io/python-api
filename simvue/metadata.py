"""
Metadata
========

Contains functions for extracting additional metadata about the current project

"""

import contextlib
import typing
import json
import toml
import logging
import pathlib
import flatdict

from simvue.utilities import simvue_timestamp

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
                "authors": json.dumps(list(author_list)),
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


def _python_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Python dependencies if lock file is available"""
    python_meta: dict[str, str] = {}

    if (pyproject_file := pathlib.Path(repository).joinpath("pyproject.toml")).exists():
        content = toml.load(pyproject_file)
        if (poetry_content := content.get("tool", {}).get("poetry", {})).get("name"):
            python_meta |= {
                "python.project.name": poetry_content["name"],
                "python.project.version": poetry_content["version"],
            }
        elif other_content := content.get("project"):
            python_meta |= {
                "python.project.name": other_content["name"],
                "python.project.version": other_content["version"],
            }

    if (poetry_lock_file := pathlib.Path(repository).joinpath("poetry.lock")).exists():
        content = toml.load(poetry_lock_file).get("package", {})
        python_meta |= {
            f"python.environment.{package['name']}": package["version"]
            for package in content
        }
    elif (uv_lock_file := pathlib.Path(repository).joinpath("uv.lock")).exists():
        content = toml.load(uv_lock_file).get("package", {})
        python_meta |= {
            f"python.environment.{package['name']}": package["version"]
            for package in content
        }
    else:
        with contextlib.suppress((KeyError, ImportError)):
            from pip._internal.operations.freeze import freeze

            python_meta |= {
                f"python.environment.{entry[0]}": entry[-1]
                for line in freeze(local_only=True)
                if (entry := line.split("=="))
            }

    return python_meta


def _rust_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Rust dependencies if lock file available"""
    rust_meta: dict[str, str] = {}

    if (cargo_file := pathlib.Path(repository).joinpath("Cargo.toml")).exists():
        content = toml.load(cargo_file).get("package", {})
        if version := content.get("version"):
            rust_meta |= {"rust.project.version": version}

        if name := content.get("name"):
            rust_meta |= {"rust.project.name": name}

    if not (cargo_lock := pathlib.Path(repository).joinpath("Cargo.lock")).exists():
        return {}

    cargo_dat = toml.load(cargo_lock)

    return rust_meta | {
        f"rust.environment.{dependency['name']}": dependency["version"]
        for dependency in cargo_dat.get("package")
    }


def _julia_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Julia dependencies if a project file is available"""
    julia_meta: dict[str, str] = {}
    if (project_file := pathlib.Path(repository).joinpath("Project.toml")).exists():
        content = toml.load(project_file)
        julia_meta |= {
            f"julia.project.{key}": value
            for key, value in content.items()
            if not isinstance(value, dict)
        }
        julia_meta |= {
            f"julia.environment.{key}": value
            for key, value in content.get("compat", {}).items()
        }
    return julia_meta


def _node_js_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    js_meta: dict[str, str] = {}
    if (
        project_file := pathlib.Path(repository).joinpath("package-lock.json")
    ).exists():
        content = json.load(project_file.open())
        if (lfv := content["lockfileVersion"]) not in (1, 2, 3):
            logger.warning(
                f"Unsupported package-lock.json lockfileVersion {lfv}, ignoring JS project metadata"
            )
            return {}

        js_meta |= {
            f"javascript.project.{key}": value
            for key, value in content.items()
            if key in ("name", "version")
        }
        js_meta |= {
            f"javascript.environment.{key.replace('@', '')}": value["version"]
            for key, value in content.get(
                "packages" if lfv in (2, 3) else "dependencies", {}
            ).items()
            if key and not value.get("dev", True)
        }
    return js_meta


def environment(repository: pathlib.Path = pathlib.Path.cwd()) -> dict[str, typing.Any]:
    """Retrieve environment metadata"""
    _environment_meta = flatdict.FlatDict(
        _python_env(repository), delimiter="."
    ).as_dict()
    _environment_meta |= flatdict.FlatDict(
        _rust_env(repository), delimiter="."
    ).as_dict()
    _environment_meta |= flatdict.FlatDict(
        _julia_env(repository), delimiter="."
    ).as_dict()
    _environment_meta |= flatdict.FlatDict(
        _node_js_env(repository), delimiter="."
    ).as_dict()
    return _environment_meta
