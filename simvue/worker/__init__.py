import threading
import typing

import msgpack

import simvue.api as sv_api
from simvue.worker.dispatch import Dispatcher


class Worker:
    def __init__(self, run_id: str, url: str, headers: dict[str, str]) -> None:
        self._url = url
        self._run_id = run_id
        self._headers = headers
        self._termination_trigger = threading.Event()
        self._dispatcher = Dispatcher(
            callback=self._create_online_callback(),
            termination_trigger=self._termination_trigger,
            queue_categories=["events", "metrics"],
        )

    def _create_online_callback(self) -> typing.Callable[[list[typing.Any], str], None]:
        def _heartbeat(
            url: str = self._url,
            headers: dict[str, str] = self._headers,
            run_id: str = self._run_id,
        ) -> None:
            _data = {"id": run_id}
            sv_api.put(f"{url}/api/runs", headers=headers, data=_data)

        def _online_dispatch_callback(
            data: list[typing.Any], category: str, url=self._url, headers=self._headers
        ) -> None:
            _data_bin = msgpack.packb(data, use_bin_type=True)
            _url: str = f"{url}/api/{category}"

            sv_api.post(url=_url, headers=headers, data=_data_bin, is_json=False)

        return _online_dispatch_callback
