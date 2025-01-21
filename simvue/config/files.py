"""
Simvue Config File Lists
========================

Contains lists of valid Simvue configuration file names.

"""

import pathlib

CONFIG_FILE_NAMES: list[str] = ["simvue.toml", ".simvue.toml"]

CONFIG_INI_FILE_NAMES: list[str] = [
    f"{pathlib.Path.cwd().joinpath('simvue.ini')}",
    f"{pathlib.Path.home().joinpath('.simvue.ini')}",
]

DEFAULT_OFFLINE_DIRECTORY: str = f"{pathlib.Path.home().joinpath('.simvue')}"
