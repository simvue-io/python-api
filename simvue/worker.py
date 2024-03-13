"""
Simvue Remote Worker
====================

Contains a class for handling the buffering and preparation of data for
submission to the Simvue server, preventing high frequency requests.
"""

import contextlib
import datetime
import json
import logging
import multiprocessing
import os
import queue
import threading
import time
import typing

import msgpack
import psutil
from typing_extensions import Buffer

from .metrics import get_gpu_metrics, get_process_cpu, get_process_memory
from .utilities import create_file, get_offline_directory

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 60
POLLING_INTERVAL = 20
MAX_BUFFER_SEND = 16000


class Worker(threading.Thread):
    def __init__(
        self,
        metrics_queue: queue.Queue,
        events_queue: queue.Queue[typing.Any],
        shutdown_event: threading.Event,
        uuid: str,
        run_name: str,
        run_id: str,
        url: str,
        headers: dict[str, str],
        mode: str,
        pid: int,
        resources_metrics_interval: float,
        suppress_errors: bool = True,
    ) -> None:
        threading.Thread.__init__(self)
        self._parent_thread: threading.Thread = threading.current_thread()
        self._metrics_queue = metrics_queue
        self._events_queue = events_queue
        self._shutdown_event = shutdown_event
        self._run_name = run_name
        self._run_id = run_id
        self._uuid = uuid
        self._url = url
        self._headers = headers
        self._headers_mp = headers.copy()
        self._headers_mp["Content-Type"] = "application/msgpack"
        self._mode = mode
        self._directory = os.path.join(get_offline_directory(), self._uuid)
        self._start_time = time.time()
        self._suppress_errors = suppress_errors
        self._resources_metrics_interval = resources_metrics_interval
        self._parent_process = psutil.Process(pid) if pid else None

        os.makedirs(self._directory, exist_ok=True)

        logger.debug("Worker thread started")

    @property
    def processes(self) -> list[psutil.Process]:
        """
        Create an array containing a list of processes
        """
        if not self._parent_process:
            return []

        _all_processes: list[psutil.Process] = [self._parent_process]

        with contextlib.suppress(psutil.NoSuchProcess, psutil.ZombieProcess):
            for child in self._parent_process.children(recursive=True):
                if child not in _all_processes:
                    _all_processes.append(child)

        return list(set(_all_processes))

    def heartbeat(self) -> None:
        """
        Send a heartbeat
        """
        data = {"id": self._run_id}

        if self._mode == "online":
            from .api import put

            put(f"{self._url}/api/runs/heartbeat", self._headers, data)
        else:
            create_file(f"{self._directory}/heartbeat")

    def post(self, endpoint, data) -> bool:
        """
        Send the supplied data
        """
        if self._mode == "online":
            from .api import post

            post(
                f"{self._url}/api/{endpoint}",
                self._headers_mp,
                data=data,
                is_json=False,
            )
        else:
            if not os.path.isdir(self._directory):
                logger.error(
                    f"Cannot write to offline directory '{self._directory}', directory not found."
                )
                return False
            unique_id = time.time()
            filename = f"{self._directory}/{endpoint}-{unique_id}"
            try:
                with open(filename, "w") as fh:
                    json.dump(data, fh)
            except Exception as err:
                if self._suppress_errors:
                    logger.error(
                        "Got exception writing offline update for %s: %s",
                        endpoint,
                        str(err),
                    )
                else:
                    raise err

        return True

    def _send_objects(self, queue: multiprocessing.JoinableQueue, label: str) -> None:
        buffer: list[Buffer] = []

        while not queue.empty() and len(buffer) < MAX_BUFFER_SEND:
            item: Buffer = queue.get(block=False)
            buffer.append(item)
            queue.task_done()

        if not buffer:
            return

        logger.debug(f"Sending {label}")

        obj: dict[str, typing.Union[str, Buffer]] = {label: buffer, "run": self._run_id}

        try:
            if self._mode == "online":
                self.post(label, msgpack.packb(obj, use_bin_type=True))
            else:
                self.post(label, obj)
        except Exception as err:
            if self._suppress_errors:
                logger.error(f"Failed to post {label}: %s", err)
            else:
                raise err

    def _collect_sysinfo(self) -> float:
        cpu = get_process_cpu(self.processes)
        memory = get_process_memory(self.processes)
        gpu = get_gpu_metrics(self.processes)

        if memory is not None and cpu is not None:
            data = {}

            data["step"] = 0
            data["values"] = {
                "resources/cpu.usage.percent": cpu,
                "resources/memory.usage": memory,
            }
            if gpu:
                for item in gpu:
                    data["values"][item] = gpu[item]
            data["time"] = time.time() - self._start_time
            data["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

            try:
                self._metrics_queue.put(data, block=False)
            except Exception as err:
                if self._suppress_errors:
                    logger.error(
                        "Failed to add system info to submission queue: %s", err
                    )
                else:
                    raise err

        return time.time()

    def _send_all(self, record_sys_info: bool = True) -> float:
        latest_sys_info_record_time: float = 0

        if record_sys_info:
            latest_sys_info_record_time = self._collect_sysinfo()

        # Send metrics
        self._send_objects(self._metrics_queue, "metrics")

        # Send events
        self._send_objects(self._events_queue, "events")

        return latest_sys_info_record_time

    def run(self) -> None:
        """
        Loop sending heartbeats, metrics and events
        """
        last_heartbeat: float = 0
        latest_sysinfo: float = 0
        collected: bool = False

        while True:
            queues_empty: bool = (
                self._metrics_queue.empty() and self._events_queue.empty()
            )

            # If a shutdown has been called and there is nothing to transmit
            # then exit
            if queues_empty and self._shutdown_event.is_set():
                return

            # Collect metrics if necessary
            if not (
                time.time() - latest_sysinfo > self._resources_metrics_interval
                and self.processes
            ):
                continue

            # Send heartbeat if necessary
            if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                try:
                    self.heartbeat()
                    last_heartbeat = time.time()
                except Exception as err:
                    if self._suppress_errors:
                        logger.error("Error sending heartbeat: %s", str(err))
                    else:
                        raise err

            latest_sysinfo = self._send_all(collected)

            # Need to wait before sending sys info, otherwise first point will have zero CPU usage
            if not collected:
                collected = True

            if all(
                [
                    self._shutdown_event.is_set() or not self._parent_thread.is_alive(),
                    self._metrics_queue.empty() and self._events_queue.empty(),
                ]
            ):
                logger.debug("Ending worker thread")
                return
            else:
                counter = 0
                while (
                    counter < POLLING_INTERVAL
                    and not self._shutdown_event.is_set()
                    and self._parent_thread.is_alive()
                    and not self._events_queue.full()
                    and not self._metrics_queue.full()
                ):
                    time.sleep(0.1)
                    counter += 1
