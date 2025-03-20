"""
CPU/GPU Metrics
===============

Get information relating to the usage of the CPU and GPU (where applicable)

"""

import contextlib
import logging
import psutil


from .pynvml import (
    nvmlDeviceGetComputeRunningProcesses,
    nvmlDeviceGetCount,
    nvmlDeviceGetGraphicsRunningProcesses,
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetMemoryInfo,
    nvmlDeviceGetUtilizationRates,
    nvmlInit,
    nvmlShutdown,
)

RESOURCES_METRIC_PREFIX: str = "resources"

logger = logging.getLogger(__name__)


def get_process_memory(processes: list[psutil.Process]) -> int:
    """
    Get the resident set size
    """
    rss: int = 0
    for process in processes:
        with contextlib.suppress(Exception):
            rss += process.memory_info().rss / 1024 / 1024

    return rss


def get_process_cpu(
    processes: list[psutil.Process], interval: float | None = None
) -> int:
    """
    Get the CPU usage

    If first time being called, use a small interval to collect initial CPU metrics.
    """
    cpu_percent: int = 0
    for process in processes:
        with contextlib.suppress(Exception):
            cpu_percent += process.cpu_percent(interval=interval)

    return cpu_percent


def is_gpu_used(handle, processes: list[psutil.Process]) -> bool:
    """
    Check if the GPU is being used by the list of processes
    """
    pids = [process.pid for process in processes]

    gpu_pids = [process.pid for process in nvmlDeviceGetComputeRunningProcesses(handle)]
    gpu_pids.extend(
        process.pid for process in nvmlDeviceGetGraphicsRunningProcesses(handle)
    )
    return len(list(set(gpu_pids) & set(pids))) > 0


def get_gpu_metrics(processes: list[psutil.Process]) -> list[tuple[float, float]]:
    """
    Get GPU metrics
    """
    gpu_metrics: list[tuple[float, float]] = []

    with contextlib.suppress(Exception):
        nvmlInit()
        device_count = nvmlDeviceGetCount()
        for i in range(device_count):
            handle = nvmlDeviceGetHandleByIndex(i)
            if is_gpu_used(handle, processes):
                utilisation_percent = nvmlDeviceGetUtilizationRates(handle).gpu
                memory = nvmlDeviceGetMemoryInfo(handle)
                memory_percent = 100 * memory.free / memory.total
                gpu_metrics.append((utilisation_percent, memory_percent))

        nvmlShutdown()

    return gpu_metrics


class SystemResourceMeasurement:
    def __init__(
        self,
        processes: list[psutil.Process],
        interval: float | None,
        cpu_only: bool = False,
    ) -> None:
        self.cpu_percent: float | None = get_process_cpu(processes, interval=interval)
        self.cpu_memory: float | None = get_process_memory(processes)
        self.gpus: list[dict[str, float]] = (
            None if cpu_only else get_gpu_metrics(processes)
        )

    def to_dict(self) -> dict[str, float]:
        _metrics: dict[str, float] = {
            f"{RESOURCES_METRIC_PREFIX}/cpu.usage.percentage": self.cpu_percent,
            f"{RESOURCES_METRIC_PREFIX}/cpu.usage.memory": self.cpu_memory,
        }

        for i, gpu in enumerate(self.gpus or []):
            _metrics[f"{RESOURCES_METRIC_PREFIX}/gpu.utilisation.percent.{i}"] = gpu[
                "utilisation"
            ]
            _metrics[f"{RESOURCES_METRIC_PREFIX}/gpu.utilisation.memory.{i}"] = gpu[
                "memory"
            ]

        return _metrics
