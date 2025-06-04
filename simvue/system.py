"""System information retrieval."""

import contextlib
import pathlib
import platform
import shutil
import socket
import subprocess
import sys
import typing


def get_cpu_info() -> tuple[str, str]:
    """Get CPU info."""
    model_name: str = ""
    arch: str = ""

    if _lscpu := shutil.which("lscpu"):
        with contextlib.suppress(subprocess.CalledProcessError):
            info = subprocess.check_output(_lscpu).decode().strip()  # noqa: S603
            for line in info.split("\n"):
                if "Model name" in line:
                    model_name = line.split(":")[1].strip()
                if "Architecture" in line:
                    arch = line.split(":")[1].strip()

    arch = arch or platform.machine()

    if not model_name and (_sysctl := shutil.which("sysctl")):
        with contextlib.suppress(subprocess.CalledProcessError):
            info = (
                subprocess.check_output([_sysctl, "machdep.cpu.brand_string"])  # noqa: S603
                .decode()
                .strip()
            )
            if "machdep.cpu.brand_string:" in info:
                model_name = info.split("machdep.cpu.brand_string: ")[1]

    return model_name, arch


def get_gpu_info() -> dict[str, str]:
    """Get GPU info."""
    _gpu_info: dict[str, str] = {"name": "", "driver_version": ""}

    if _nvidia_smi := shutil.which("nvidia-smi"):
        with contextlib.suppress(subprocess.CalledProcessError, IndexError):
            output = subprocess.check_output(  # noqa: S603
                [_nvidia_smi, "--query-gpu=name,driver_version", "--format=csv"]
            )
            lines = output.split(b"\n")
            tokens = lines[1].split(b", ")
            _gpu_info["name"] = tokens[0].decode()
            _gpu_info["driver_version"] = tokens[1].decode()

    return _gpu_info


def get_system() -> dict[str, typing.Any]:
    """Get system details."""
    _cpu = get_cpu_info()
    _gpu = get_gpu_info()

    _cwd = pathlib.Path.cwd()
    _system: dict[str, typing.Any] = {"cwd": f"{_cwd}"}
    _system["hostname"] = socket.gethostname()
    _system["pythonversion"] = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    _system["platform"] = {}
    _system["platform"]["system"] = platform.system()
    _system["platform"]["release"] = platform.release()
    _system["platform"]["version"] = platform.version()
    _system["cpu"] = {}
    _system["gpu"]["processor"], _system["cpu"]["arch"] = _cpu
    _system["gpu"] = {}
    _system["gpu"]["name"] = _gpu["name"]
    _system["gpu"]["driver"] = _gpu["driver_version"]

    return _system
