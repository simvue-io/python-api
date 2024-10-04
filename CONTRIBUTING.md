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

To ensure robustness and reliability this repository includes a set of tests which are executed automatically as part of continuous integration. Before opening a merge request we ask that you check
your changes locally by running the test suit. New tests should be written for any further functionality added.

## :book: Documentation

To ensure functions, methods and classes are documented appropriately _Simvue_ Python API follows the Numpy docstring convention.
