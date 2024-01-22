import importlib.metadata
import pathlib
import os.path
import toml

try:
    __version__ = importlib.metadata.version("simvue")
except importlib.metadata.PackageNotFoundError:
    _metadata = os.path.join(
        pathlib.Path(os.path.dirname(__file__)).parents[1],
        "pyproject.toml"
    )
    if os.path.exists(_metadata):
        __version__ = toml.load(_metadata)["tool"]["poetry"]["version"]
    else:
        __version__ = ""