import time
import psutil
import multiprocessing

def get_process_memory(process):
    """
    Get the resident set size
    """
    try:
        rss = process.memory_info().rss/1024/1024
        for child in process.children(recursive=True):
            rss += child.memory_info().rss/1024/1024
    except:
        return None

    return rss
    
def get_process_cpu(process):
    """
    Get the CPU usage
    """
    try:
        cpu_percent = process.cpu_percent()
        for child in process.children(recursive=True):
            cpu_percent += child.cpu_percent()
    except:
        return None

    return cpu_percent
