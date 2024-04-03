import os
import platform
import socket
import subprocess
import sys
import contextlib
import typing


def get_cpu_info():
    """
    Get CPU info
    """
    model_name = ""
    arch = ""

    with contextlib.suppress(subprocess.CalledProcessError):
        info = subprocess.check_output("lscpu").decode().strip()
        for line in info.split("\n"):
            if "Model name" in line:
                model_name = line.split(":")[1].strip()
            if "Architecture" in line:
                arch = line.split(":")[1].strip()
    # TODO: Try /proc/cpuinfo if process fails

    if arch == "":
        arch = platform.machine()

    if model_name == "":
        with contextlib.suppress(subprocess.CalledProcessError):
            info = (
                subprocess.check_output(["sysctl", "machdep.cpu.brand_string"])
                .decode()
                .strip()
            )
            if "machdep.cpu.brand_string:" in info:
                model_name = info.split("machdep.cpu.brand_string: ")[1]

    return model_name, arch


def get_gpu_info():
    """
    Get GPU info
    """
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv"]
        )
        lines = output.split(b"\n")
        tokens = lines[1].split(b", ")
    except subprocess.CalledProcessError:
        return {"name": "", "driver_version": ""}

    return {"name": tokens[0].decode(), "driver_version": tokens[1].decode()}


def get_system() -> dict[str, typing.Any]:
    """
    Get system details
    """
    cpu = get_cpu_info()
    gpu = get_gpu_info()

    system: dict[str, typing.Any] = {}
    system["cwd"] = os.getcwd()
    system["hostname"] = socket.gethostname()
    system["pythonversion"] = (
        f"{sys.version_info.major}."
        f"{sys.version_info.minor}."
        f"{sys.version_info.micro}"
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
