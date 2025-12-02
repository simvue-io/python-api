import importlib.metadata
import os.path
import pathlib

import toml

try:
    __version__ = importlib.metadata.version("simvue")
except importlib.metadata.PackageNotFoundError:
    _metadata = os.path.join(
        pathlib.Path(os.path.dirname(__file__)).parents[1], "pyproject.toml"
    )
    if os.path.exists(_metadata):
        __version__ = toml.load(_metadata)["project"]["version"]
    else:
        __version__ = ""
