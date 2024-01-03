import logging
import psutil
import contextlib
import simvue.pynvml as pynvml

logger = logging.getLogger(__name__)

def get_process_memory(processes: list[psutil.Process]) -> float:
    """
    Get the resident set size
    """
    rss: float = 0

    for process in processes:
        # Handle case for if the process no longer exists
        with contextlib.suppress((psutil.NoSuchProcess, psutil.ZombieProcess)):
            rss += process.memory_info().rss / 1024 / 1024

    return rss


def get_process_cpu(processes: list[psutil.Process]) -> float:
    """
    Get the CPU usage
    """
    cpu_percent: float = 0

    for process in processes:
        # Handle case for if the process no longer exists
        with contextlib.suppress((psutil.NoSuchProcess, psutil.ZombieProcess)):
            cpu_percent += process.cpu_percent()

    return cpu_percent


def is_gpu_used(handle, processes: list[psutil.Process]) -> bool:
    """
    Check if the GPU is being used by the list of processes
    """ 
    pids: list[int] = [process.pid for process in processes]
    gpu_pids: list[int] = []

    for process in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
        gpu_pids.append(process.pid)

    for process in pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle):
        gpu_pids.append(process.pid)
        
    return len(list(set(gpu_pids) & set(pids))) > 0


def get_gpu_metrics(processes: list[psutil.Process]) -> dict[str, float]:
    """
    Get GPU metrics
    """
    gpu_metrics: dict[str, float] = {}

    with contextlib.suppress(pynvml.NVMLError):
        pynvml.nvmlInit()
        device_count: int = pynvml.nvmlDeviceGetCount()

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            
            if not is_gpu_used(handle, processes):
                continue
            
            utilisation_percent: float = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            memory: float = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_percent: float = 100 * memory.free / memory.total
            gpu_metrics[f"resources/gpu.utilisation.percent.{i}"] = utilisation_percent
            gpu_metrics[f"resources/gpu.memory.percent.{i}"] = memory_percent

        pynvml.nvmlShutdown()

    return gpu_metrics
