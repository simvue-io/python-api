import datetime
import json
import os
import psutil
import sys
import time
import threading
import requests
import msgpack

from .api import post, put
from .metrics import get_process_memory, get_process_cpu, get_gpu_metrics
from .utilities import get_offline_directory, create_file

HEARTBEAT_INTERVAL = 60
POLLING_INTERVAL = 20
MAX_BUFFER_SEND = 5000

def update_processes(parent, processes):
    """
    Create an array containing a list of processes
    """
    for child in parent.children(recursive=True):
        if child not in processes:
            processes.append(child)
    if parent not in processes:
        processes.append(parent)
    return processes


class Worker(threading.Thread):
    def __init__(self, metrics_queue, events_queue, uuid, run_name, url, headers, mode, pid, resources_metrics_interval):
        threading.Thread.__init__(self)
        self._parent_thread = threading.currentThread()
        self._metrics_queue = metrics_queue
        self._events_queue = events_queue
        self._run_name = run_name
        self._uuid = uuid
        self._url = url
        self._headers = headers
        self._headers_mp = headers.copy()
        self._headers_mp['Content-Type'] = 'application/msgpack'
        self._mode = mode
        self._directory = os.path.join(get_offline_directory(), self._uuid)
        self._start_time = time.time()
        self._processes = []
        self._resources_metrics_interval = resources_metrics_interval
        self._pid = pid
        if pid:
            self._processes = update_processes(psutil.Process(pid), [])

    def heartbeat(self):
        """
        Send a heartbeat
        """
        if self._mode == 'online':
            put(f"{self._url}/api/runs/heartbeat", self._headers, {'name': self._run_name})
        else:
            create_file(f"{self._directory}/heartbeat")

    def post(self, endpoint, data):
        """
        Send the supplied data
        """
        if self._mode == 'online':
            post(f"{self._url}/api/{endpoint}", self._headers_mp, data=data, is_json=False)
        else:
            unique_id = time.time()
            filename = f"{self._directory}/{endpoint}-{unique_id}"
            with open(filename, 'w') as fh:
                json.dump(data, fh)

    def run(self):
        """
        Loop sending heartbeats, metrics and events
        """
        last_heartbeat = 0
        last_metrics = 0
        collected = False
        while True:
            # Collect metrics if necessary
            if time.time() - last_metrics > self._resources_metrics_interval and self._processes:
                if self._pid:
                    self._processes = update_processes(psutil.Process(self._pid), self._processes)
                cpu = get_process_cpu(self._processes)
                if not collected:
                    # Need to wait before sending metrics, otherwise first point will have zero CPU usage
                    collected = True
                else:
                    memory = get_process_memory(self._processes)
                    gpu = get_gpu_metrics(self._processes)
                    if memory is not None and cpu is not None:
                        data = {}
                        data['step'] = 0
                        data['run'] = self._run_name
                        data['values'] = {'resources/cpu.usage.percent': cpu,
                                          'resources/memory.usage': memory}
                        if gpu:
                            for item in gpu:
                                data['values'][item] = gpu[item]
                        data['time'] = time.time() - self._start_time
                        data['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                        try:
                            self._metrics_queue.put(data, block=False)
                        except:
                            pass
                    last_metrics = time.time()

            # Send heartbeat if necessary
            if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                try:
                    self.heartbeat()
                except:
                    pass
                last_heartbeat = time.time()

            # Send metrics
            buffer = []
            while not self._metrics_queue.empty() and len(buffer) < MAX_BUFFER_SEND:
                item = self._metrics_queue.get(block=False)
                buffer.append(item)
                self._metrics_queue.task_done()

            if buffer:
                try:
                    if self._mode == 'online': buffer = msgpack.packb(buffer, use_bin_type=True)
                    self.post('metrics', buffer)
                except:
                    pass
                buffer = []

            # Send events
            buffer = []
            while not self._events_queue.empty() and len(buffer) < MAX_BUFFER_SEND:
                item = self._events_queue.get(block=False)
                buffer.append(item)
                self._events_queue.task_done()

            if buffer:
                try:
                    if self._mode == 'online': buffer = msgpack.packb(buffer, use_bin_type=True)
                    self.post('events', buffer)
                except:
                    pass
                buffer = []

            if not self._parent_thread.is_alive():
                if self._metrics_queue.empty() and self._events_queue.empty():
                    sys.exit(0)
            else:
                time.sleep(POLLING_INTERVAL)
