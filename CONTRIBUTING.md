# Contributing to Simvue Python API

Contributions to improve and enhance the Python API for _Simvue_ are very welcome,
we ask that such modifications are made by firstly opening an issue outlining the fix or change allowing for discussion, then creating a feature branch on which to develop.
Where possible development should be carried out with the latest stable release of Python to ensure any functionality remains future proof.

## :memo: Issue Creation

When opening an issue please ensure you outline in as much detail as possible the issues or proposed changes you wish to develop. Also ensure that this feature/fix has not already been raised by firstly searching through all current issues.

If reporting a bug, provide as much detail outlining a minimal example and describing any useful specifications and outlining the scenario which led to the problem.

## 🧰 Development

### :closed_book: Python Poetry

For development it is strongly recommended that [Poetry](https://python-poetry.org) be used to manage dependencies and create the virtual environment used for development, the included `pyproject.toml` file makes use of the framework for ensuring dependency compatibility and building of the module during deployment. The included `poetry.lock` file defines the virtual environment to ensure the developers are running the `simvue` in an identical manner. Install poetry and setup the virtual environment by running from the root of this repository:

```sh
pip install --user poetry
poetry install
```

### 🪝 Using Git hooks

Included within this repository are a set of Git hooks which ensure consistency in formating and prevent the accidental inclusion of non-code based files. The hooks are installed using the [`pre-commit`](https://pre-commit.com/) tool. Use of these hooks is recommended as they are also run as a verification step of the continuous integration pipeline. To setup pre-commit, change directory to the root of this repository and run:

```sh
pip install --user pre-commit
pre-commit install
```

### 🧪 Testing

To ensure robustness and reliability this repository includes a set of tests which are executed automatically as part of continuous integration. Before opening a merge request we ask that you check your changes locally by running the test suite. New tests should be written for any further functionality added.

```sh
pytest tests
```

### 🌿 Using the Right Branch

In order to fix previous versions, minor versions each have their own branch. This branch is created prior to the release of `vX.Y`. At this point there should be no new features added, with only bug fixes being applied.

Remember if working on a fix for a particular minor version, checkout and branch from the branch for that version, and make sure to select the appropriate version branch when opening an MR. For example a bug fix for `v1.1` made on a new branch `hotfix/fix-that-bug` created from the `v1.1` branch, would then be merged back into the `v1.1` branch.

Development of new features, or towards the latest version should be made on branches created from `dev` which must always contain the latest version. Such branches should, where possible, contain only a single new feature and be labelled `feature/<feature-description>`.

The branch `main` contains only tagged releases, the idea being all commits on this branch are usable versions.

### ℹ️ Typing

All code within this repository makes use of Python's typing capability, this has proven invaluable for spotting any incorrect usage of functionality as linters are able to quickly flag up any incompatibilities. Typing also allows us define validator rules using the [Pydantic](https://docs.pydantic.dev/latest/) framework.  We ask that you type all functions and variables where possible.

### ✔️ Linting and Formatting

_Simvue_ Python API utilises the [Ruff](https://github.com/astral-sh/ruff) linter and formatter to ensure consistency, and this tool is included as part of the pre-commit hooks. Checking of styling/formatting is part of the CI pipeline.

## :book: Documentation

To ensure functions, methods and classes are documented appropriately _Simvue_ Python API follows the Numpy docstring convention. We also ask that if adding new features you ensure these are mentioned within the official [documentation](https://github.com/simvue-io/docs).
