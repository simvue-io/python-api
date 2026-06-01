import importlib.metadata
import pathlib

import toml

try:
    __version__ = importlib.metadata.version("simvue")
except importlib.metadata.PackageNotFoundError:
    _metadata = (
        pathlib.Path(__file__)
        .parents[2]
        .joinpath(
            "pyproject.toml",
        )
    )
    if _metadata.exists():
        __version__ = toml.load(_metadata)["project"]["version"]
    else:
        __version__ = ""
