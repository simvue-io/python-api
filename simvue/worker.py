import multiprocessing
import sys
import time
import threading
import requests

HEARTBEAT_INTERVAL = 60
POLLING_INTERVAL = 2

class Worker(threading.Thread):
    def __init__(self, metrics_queue, events_queue, name, url, headers):
        threading.Thread.__init__(self)
        self._parent_thread = threading.currentThread()
        self._metrics_queue = metrics_queue
        self._events_queue = events_queue
        self._name = name
        self._url = url
        self._headers = headers

    def run(self):
        last_heartbeat = 0
        while True:
            # Send heartbeat
            if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                try:
                    requests.put('%s/api/runs/heartbeat' % self._url, headers=self._headers, json={'name': self._name})
                    last_heartbeat = time.time()
                except:
                    pass

            # Send metrics
            buffer = []
            while not self._metrics_queue.empty():
                item = self._metrics_queue.get(block=False)
                buffer.append(item)
                self._metrics_queue.task_done()

            if buffer:
                try:
                    response = requests.post('%s/api/metrics' % self._url, headers=self._headers, json=buffer)
                except:
                    pass

            # Send events
            buffer = []
            while not self._events_queue.empty():
                item = self._events_queue.get(block=False)
                buffer.append(item)
                self._events_queue.task_done()

            if buffer:
                try:
                    requests.post('%s/api/events' % self._url, headers=self._headers, json=buffer)
                except:
                    pass

            if not self._parent_thread.is_alive():
                sys.exit(0)

            time.sleep(POLLING_INTERVAL)
