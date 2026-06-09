"""Retrieve System Information for Metrics."""

import contextlib
import pathlib
import platform
import shutil
import socket
import subprocess  # noqa: S404
import sys
import typing


def get_cpu_info() -> tuple[str, str]:
    """Get CPU info."""
    model_name = ""
    arch = ""

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
                subprocess  # noqa: S603
                .check_output([_sysctl, "machdep.cpu.brand_string"])
                .decode()
                .strip()
            )
            if "machdep.cpu.brand_string:" in info:
                model_name = info.split("machdep.cpu.brand_string: ")[1]

    return model_name, arch


def get_gpu_info() -> dict[str, str]:
    """Get GPU info."""
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
    """Get system details."""
    cpu = get_cpu_info()
    gpu = get_gpu_info()

    system: dict[str, typing.Any] = {"cwd": f"{pathlib.Path.cwd()}"}
    system["hostname"] = socket.gethostname()
    system["pythonversion"] = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    system["platform"] = {}
    system["platform"]["system"] = platform.system()
    system["platform"]["release"] = platform.release()
    system["platform"]["version"] = platform.version()
    system["cpu"] = {}
    system["cpu"]["arch"] = cpu[1]
    system["cpu"]["processor"] = cpu[0]
    system["gpu"] = {}
    system["gpu"]["name"] = gpu["name"]
    system["gpu"]["driver"] = gpu["driver_version"]

    return system
