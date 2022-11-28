import time
import psutil

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
