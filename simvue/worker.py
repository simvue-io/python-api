import os
import sys
import time
import threading
import requests
import msgpack
from tenacity import retry, wait_exponential, stop_after_attempt

from .utilities import get_offline_directory, get_directory_name, create_file

HEARTBEAT_INTERVAL = 60
POLLING_INTERVAL = 1
MAX_BUFFER_SEND = 5000

class Worker(threading.Thread):
    def __init__(self, metrics_queue, events_queue, name, url, headers, mode):
        threading.Thread.__init__(self)
        self._parent_thread = threading.currentThread()
        self._metrics_queue = metrics_queue
        self._events_queue = events_queue
        self._name = name
        self._url = url
        self._headers = headers
        self._headers_mp = headers.copy()
        self._headers_mp['Content-Type'] = 'application/msgpack'
        self._mode = mode
        self._directory = os.path.join(get_offline_directory(), get_directory_name(name))

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
    def heartbeat(self):
        """
        Send a heartbeat, with retries
        """
        if self._mode == 'online':
            response = requests.put(f"{self._url}/api/runs/heartbeat",
                                    headers=self._headers,
                                    json={'name': self._name})
            response.raise_for_status()
        else:
            create_file(f"{self._directory}/heartbeat")

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
    def post(self, endpoint, data):
        """
        Send the supplied data, with retries
        """
        if self._mode == 'online':
            response = requests.post(f"{self._url}/api/{endpoint}",
                                     headers=self._headers_mp,
                                     data=data)
            response.raise_for_status()
        else:
            unique_id = time.time()
            filename = f"{self._directory}/{endpoint}-{unique_id}"
            with open(filename, 'wb') as fh:
                fh.write(data)

    def run(self):
        """
        Loop sending heartbeats, metrics and events
        """
        last_heartbeat = 0
        while True:
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
                    self.post('metrics', msgpack.packb(buffer, use_bin_type=True))
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
                    self.post('events', msgpack.packb(buffer, use_bin_type=True))
                except:
                    pass
                buffer = []

            if not self._parent_thread.is_alive():
                if self._metrics_queue.empty() and self._events_queue.empty():
                    sys.exit(0)
            else:
                time.sleep(POLLING_INTERVAL)
