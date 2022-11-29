import time
import psutil
import pynvml

def get_process_memory(processes):
    """
    Get the resident set size
    """
    rss = 0
    for process in processes:
        try:
            rss += process.memory_info().rss/1024/1024
        except:
            pass

    return rss
    
def get_process_cpu(processes):
    """
    Get the CPU usage
    """
    cpu_percent = 0
    for process in processes:
        try:
            cpu_percent += process.cpu_percent()
        except:
            pass

    return cpu_percent

def is_gpu_used(handle, processes):
    """
    Check if the GPU is being used by the list of processes
    """ 
    pids = [process.pid for process in processes]

    gpu_pids = []
    for process in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
        gpu_pids.append(process.pid)

    for process in pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle):
        gpu_pids.append(process.pid)
        
    return len(list(set(gpu_pids) & set(pids))) > 0

def get_gpu_metrics(processes):
    """
    Get GPU metrics
    """
    gpu_metrics = {}

    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            if is_gpu_used(handle, processes):
                utilisation_percent = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                memory_percent = 100*memory.free/memory.total
                gpu_metrics[f"resources/gpu.utilisation.percent.{i}"] = utilisation_percent
                gpu_metrics[f"resources/gpu.memory.percent.{i}"] = memory_percent
        pynvml.nvmlShutdown()
    except:
        pass

    return gpu_metrics
