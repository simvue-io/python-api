"""Retrieve System Information."""

import contextlib
import pathlib
import platform
import shutil
import socket
import subprocess  # noqa: S404
import sys
import typing


def get_cpu_info() -> tuple[str, str]:
    """Retrieve current system CPU information.

    Returns
    -------
    tuple[str, str]
        CPU model name
        CPU architecture
    """
    _model_name: str = ""
    _arch: str = ""

    if _lscpu := shutil.which("lscpu"):
        with contextlib.suppress(subprocess.CalledProcessError):
            _info = subprocess.check_output(_lscpu).decode().strip()  # noqa: S603
            for line in _info.split("\n"):
                if "Model name" in line:
                    _model_name = line.split(":")[1].strip()
                if "Architecture" in line:
                    _arch = line.split(":")[1].strip()

    _arch = _arch or platform.machine()

    if not _model_name and (_sysctl := shutil.which("sysctl")):
        with contextlib.suppress(subprocess.CalledProcessError):
            info = (
                subprocess  # noqa: S603
                .check_output([_sysctl, "machdep.cpu.brand_string"])
                .decode()
                .strip()
            )
            if "machdep.cpu.brand_string:" in info:
                _model_name = info.split("machdep.cpu.brand_string: ")[1]

    return _model_name, _arch


def get_gpu_info() -> dict[str, str]:
    """Retrieve current system GPU info.

    If a GPU is available retrieve information on the hardware.

    Returns
    -------
    dict[str, str]
        information on GPU name and drivers
    """
    _gpu_info: dict[str, str] = {"name": "", "driver_version": ""}

    if not (_nvidia_smi := shutil.which("nvidia-smi")):
        return _gpu_info

    with contextlib.suppress(subprocess.CalledProcessError, IndexError):
        output = subprocess.check_output(  # noqa: S603
            [_nvidia_smi, "--query-gpu=name,driver_version", "--format=csv"],
        )
        lines = output.split(b"\n")
        tokens = lines[1].split(b", ")
        _gpu_info["name"] = tokens[0].decode()
        _gpu_info["driver_version"] = tokens[1].decode()

    return _gpu_info


def get_system() -> dict[str, typing.Any]:
    """Retrieve information on the current system.

    Gathers various metadata on the current system including current user,
    hardware specifictions, Python version etc.

    Returns
    -------
    dict[str, Any]
        a dictionary containing gathered system information
    """
    _cpu = get_cpu_info()
    _gpu = get_gpu_info()

    _system: dict[str, typing.Any] = {"cwd": f"{pathlib.Path.cwd()}"}
    _system["hostname"] = socket.gethostname()
    _system["pythonversion"] = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    _system["platform"] = {}
    _system["platform"]["system"] = platform.system()
    _system["platform"]["release"] = platform.release()
    _system["platform"]["version"] = platform.version()
    _system["cpu"] = {}
    _system["cpu"]["arch"] = _cpu[1]
    _system["cpu"]["processor"] = _cpu[0]
    _system["gpu"] = {}
    _system["gpu"]["name"] = _gpu["name"]
    _system["gpu"]["driver"] = _gpu["driver_version"]

    return _system
