"""
Metadata
========

Contains functions for extracting additional metadata about the current project

"""

import typing
import re
import json
from git import repo
from git.refs.reference import require_remote_ref_path
import toml
import importlib.metadata
import pathlib
import pip


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
        author_list: set[str] = set(
            email
            for commit in git_repo.iter_commits("--all")
            if "noreply" not in (email := (commit.author.email or ""))
            and "[bot]" not in (commit.author.name or "")
        )

        ref: str = current_commit.hexsha

        # In the case where the repository is dirty blame should point to the
        # current developer, not the person responsible for the latest commit
        if dirty := git_repo.is_dirty():
            blame = git_repo.config_reader().get_value("user", "email", "unknown")
        else:
            blame = current_commit.committer.email

        for tag in git_repo.tags:
            if tag.commit == current_commit:
                ref = tag.name
                break

        return {
            "git.authors": json.dumps(list(author_list)),
            "git.ref": ref,
            "git.msg": current_commit.message.strip(),
            "git.time_stamp": current_commit.committed_datetime.strftime(
                "%Y-%m-%d %H:%M:%S %z UTC"
            ),
            "git.blame": blame,
            "git.url": git_repo.remote().url,
            "git.dirty": dirty,
        }
    except (git.InvalidGitRepositoryError, ValueError):
        return {}


def _python_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Python dependencies if a file is available"""
    meta: dict[str, str] = {}
    req_meta: dict[str, str] = {}

    if (reqfile := pathlib.Path(repository).joinpath("requirements.txt")).exists():
        with reqfile.open("w") as in_req:
            requirement_lines = in_req.readlines()
            req_meta = {}

            for line in requirement_lines:
                dependency, version = line.split("=", 1)
                req_meta[dependency] = version
    if (pptoml := pathlib.Path(repository).joinpath("pyproject.toml")).exists():
        content = toml.load(pptoml)

        requirements = (project := content.get("project", {})).get("dependencies")

        if requirements:
            requirements = [re.split("[=><]", dep, 1)[0] for dep in requirements]

        requirements = requirements or (project := content.get("tool", {}).get("poetry", {})).get("dependencies")

        if (version := project.get("version")):
            meta |= {"python.project.version": version}

        if (name := project.get("name")):
            meta |= {"python.project.name": name}

        if not requirements:
            return meta

        req_meta = {
            package: importlib.metadata.version(package)
            for package in requirements if package != "python"
        }


    return meta | {
        f"python.environment.{dependency}": version
        for dependency, version in req_meta.items()
    }


def _rust_env(repository: pathlib.Path) -> dict[str, typing.Any]:
    """Retrieve a dictionary of Rust dependencies if lock file available"""
    rust_meta: dict[str, str] = {}

    if (cargo_file := pathlib.Path(repository).joinpath("Cargo.toml")).exists():
        content = toml.load(cargo_file).get("package", {})
        if (version := content.get("version")):
            rust_meta |= {"rust.project.version": version}

        if (name := content.get("name")):
            rust_meta |= {"rust.project.name": name}


    if not (cargo_lock := pathlib.Path(repository).joinpath("Cargo.lock")).exists():
        return {}

    cargo_dat = toml.load(cargo_lock)

    return rust_meta | {
        f"rust.environment.{dependency['name']}": dependency['version']
        for dependency in cargo_dat.get("package")
    }


def environment(repository: pathlib.Path=pathlib.Path.cwd()) -> dict[str, typing.Any]:
    """Retrieve environment metadata"""
    return _python_env(repository) | _rust_env(repository)

