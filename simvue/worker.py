import sys
import time
import threading
import requests
import msgpack
from tenacity import retry, wait_exponential, stop_after_attempt

HEARTBEAT_INTERVAL = 60
POLLING_INTERVAL = 1
MAX_BUFFER_SEND = 5000

class Worker(threading.Thread):
    def __init__(self, metrics_queue, events_queue, name, url, headers):
        threading.Thread.__init__(self)
        self._parent_thread = threading.currentThread()
        self._metrics_queue = metrics_queue
        self._events_queue = events_queue
        self._name = name
        self._url = url
        self._headers = headers
        self._headers_mp = headers.copy()
        self._headers_mp['Content-Type'] = 'application/msgpack'

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
    def heartbeat(self):
        """
        Send a heartbeat, with retries
        """
        response = requests.put('%s/api/runs/heartbeat' % self._url,
                                headers=self._headers,
                                json={'name': self._name})
        response.raise_for_status()

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
    def post(self, endpoint, data):
        """
        Send the supplied data, with retries
        """
        response = requests.post('%s/api/%s' % (self._url, endpoint),
                                 headers=self._headers_mp,
                                 data=data)
        response.raise_for_status()

    def run(self):
        """
        Loop sending heartbeats, metrics and events
        """
        last_heartbeat = 0
        while True:
            # Send heartbeat
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
