import logging
import time
import typing

from simvue.api import post, put, get
from simvue.utilities import (
    get_auth,
    get_expiry,
    prepare_for_api,
    get_server_version,
    skip_if_failed,
)
from simvue.factory.base import SimvueBaseClass

from simvue.version import __version__

logger = logging.getLogger(__name__)

UPLOAD_TIMEOUT: int = 30
DEFAULT_API_TIMEOUT: int = 10


class Remote(SimvueBaseClass):
    """
    Class which interacts with Simvue REST API
    """

    def __init__(self, name: str, uniq_id: str, suppress_errors: bool = True) -> None:
        self._url, self._token = get_auth()
        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {self._token}",
            "User-Agent": f"Simvue Python client {__version__}",
        }
        self._headers_mp: dict[str, str] = self._headers | {
            "Content-Type": "application/msgpack"
        }
        self._version: int | None = get_server_version()
        super().__init__(name, uniq_id, suppress_errors)

    @skip_if_failed("_aborted", "_suppress_errors", (None, None))
    def create_run(self, data) -> typing.Tuple[str | None, int | None]:
        """
        Create a run
        """
        logger.debug('Creating run with data: "%s"', data)

        try:
            response = post(f"{self._url}/api/runs", self._headers, data)
        except Exception as err:
            self._error(f"Exception creating run: {str(err)}")
            return (None, None)

        logger.debug(
            'Got status code %d when creating run, with response: "%s"',
            response.status_code,
            response.text,
        )

        if response.status_code == 409:
            self._error(f"Duplicate run, name {data['name']} already exists")
            return (None, None)
        elif response.status_code != 200:
            self._error(f"Got status code {response.status_code} when creating run")
            return (None, None)

        if "name" in response.json():
            self._name = response.json()["name"]

        if "id" in response.json():
            self._id = response.json()["id"]

        return self._name, self._id

    @skip_if_failed("_aborted", "_suppress_errors", None)
    def update(
        self, data: dict[str, typing.Any], _=None
    ) -> dict[str, typing.Any] | None:
        """
        Update metadata, tags or status
        """
        if self._id:
            data["id"] = self._id
        
        data.pop("name", None)

        logger.debug('Updating run with data: "%s"', data)

        try:
            response = put(f"{self._url}/api/runs", self._headers, data)
        except Exception as err:
            self._error(f"Exception updating run: {err}")
            return None

        logger.debug(
            'Got status code %d when updating run, with response: "%s"',
            response.status_code,
            response.text,
        )

        if response.status_code == 200:
            return data

        self._error(f"Got status code {response.status_code} when updating run")
        return None

    @skip_if_failed("_aborted", "_suppress_errors", None)
    def set_folder_details(self, data, run=None) -> dict[str, typing.Any] | None:
        """
        Set folder details
        """
        if run is not None and not self._version:
            data["name"] = run

        try:
            response = post(f"{self._url}/api/folders", self._headers, data)
        except Exception as err:
            self._error(f"Exception creatig folder: {err}")
            return None

        if response.status_code == 200 or response.status_code == 409:
            folder_id = response.json()["id"]
            data["id"] = folder_id

            if response.status_code == 200:
                logger.debug('Got id of new folder: "%s"', folder_id)
            else:
                logger.debug('Got id of existing folder: "%s"', folder_id)

        logger.debug('Setting folder details with data: "%s"', data)

        try:
            response = put(f"{self._url}/api/folders", self._headers, data)
        except Exception as err:
            self._error(f"Exception setting folder details: {err}")
            return None

        logger.debug(
            'Got status code %d when setting folder details, with response: "%s"',
            response.status_code,
            response.text,
        )

        if response.status_code == 200:
            return response.json()

        self._error(
            f"Got status code {response.status_code} when updating folder details"
        )
        return None

    @skip_if_failed("_aborted", "_suppress_errors", False)
    def save_file(self, data: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
        """
        Save file
        """
        logger.debug('Getting presigned URL for saving artifact, with data: "%s"', data)

        # Get presigned URL
        try:
            response = post(
                f"{self._url}/api/artifacts", self._headers, prepare_for_api(data)
            )
        except Exception as err:
            self._error(
                f"Got exception when preparing to upload file {data['name']} to object storage: {str(err)}"
            )
            return None

        logger.debug(
            'Got status code %d when getting presigned URL, with response: "%s"',
            response.status_code,
            response.text,
        )

        if response.status_code == 409:
            return data

        if response.status_code != 200:
            self._error(
                f"Got status code {response.status_code} when registering file {data['name']}"
            )
            return None

        storage_id = None
        if "storage_id" in response.json():
            storage_id = response.json()["storage_id"]

        if not storage_id:
            return None

        if "url" in response.json():
            url = response.json()["url"]
            if "pickled" in data and "pickledFile" not in data:
                try:
                    response = put(
                        url, {}, data["pickled"], is_json=False, timeout=UPLOAD_TIMEOUT
                    )

                    logger.debug(
                        "Got status code %d when uploading artifact",
                        response.status_code,
                    )

                    if response.status_code != 200:
                        self._error(
                            f"Got status code {response.status_code} when uploading object {data['name']} to object storage"
                        )
                        return None
                except Exception as err:
                    self._error(
                        f"Got exception when uploading object {data['name']} to object storage: {str(err)}"
                    )
                    return None
            else:
                if "pickledFile" in data:
                    use_filename = data["pickledFile"]
                else:
                    use_filename = data["originalPath"]

                try:
                    with open(use_filename, "rb") as fh:
                        response = put(
                            url, {}, fh, is_json=False, timeout=UPLOAD_TIMEOUT
                        )

                        logger.debug(
                            "Got status code %d when uploading artifact",
                            response.status_code,
                        )

                        if response.status_code != 200:
                            self._error(
                                f"Got status code {response.status_code} when uploading file {data['name']} to object storage"
                            )
                            return None
                except Exception as err:
                    self._error(
                        f"Got exception when uploading file {data['name']} to object storage: {str(err)}"
                    )
                    return None

        if storage_id:
            path = f"{self._url}/api/runs/{self._id}/artifacts"
            data["storage"] = storage_id

            try:
                response = put(path, self._headers, prepare_for_api(data))
            except Exception as err:
                self._error(
                    f"Got exception when confirming upload of file {data['name']}: {str(err)}"
                )
                return None

            if response.status_code != 200:
                self._error(
                    f"Got status code {response.status_code} when confirming upload of file {data['name']}: {response.text}"
                )
                return None

        return data

    @skip_if_failed("_aborted", "_suppress_errors", False)
    def add_alert(self, data, run=None):
        """
        Add an alert
        """
        if run is not None:
            data["run"] = run

        logger.debug('Adding alert with data: "%s"', data)

        try:
            response = post(f"{self._url}/api/alerts", self._headers, data)
        except Exception as err:
            self._error(f"Got exception when creating an alert: {str(err)}")
            return False

        logger.debug(
            'Got response %d when adding alert, with response: "%s"',
            response.status_code,
            response.text,
        )

        if response.status_code in (200, 409):
            return response.json()

        self._error(f"Got status code {response.status_code} when creating alert")
        return False

    @skip_if_failed("_aborted", "_suppress_errors", {})
    def set_alert_state(self, alert_id, status) -> dict[str, typing.Any] | None:
        """
        Set alert state
        """
        data = {"run": self._id, "alert": alert_id, "status": status}
        try:
            response = put(f"{self._url}/api/alerts/status", self._headers, data)
        except Exception as err:
            self._error(f"Got exception when setting alert state: {err}")
            return {}

        if response.status_code == 200:
            return response.json()

        return {}

    @skip_if_failed("_aborted", "_suppress_errors", [])
    def list_alerts(self) -> list[dict[str, typing.Any]]:
        """
        List alerts
        """
        try:
            response = get(f"{self._url}/api/alerts", self._headers)
        except Exception as err:
            self._error(f"Got exception when listing alerts: {str(err)}")
            return []

        if response.status_code == 200:
            return response.json()

        return []

    @skip_if_failed("_aborted", "_suppress_errors", None)
    def send_metrics(self, data: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
        """
        Send metrics
        """
        logger.debug("Sending metrics")

        raise Exception(data)

        try:
            response = post(
                f"{self._url}/api/metrics", self._headers_mp, data, is_json=False
            )
        except Exception as err:
            self._error(f"Exception sending metrics: {str(err)}")
            return None

        logger.debug("Got status code %d when sending metrics", response.status_code)

        if response.status_code == 200:
            return response.json()

        self._error(f"Got status code {response.status_code} when sending metrics")
        return None

    @skip_if_failed("_aborted", "_suppress_errors", None)
    def send_event(self, data: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
        """
        Send events
        """
        logger.debug("Sending events")

        try:
            response = post(
                f"{self._url}/api/events", self._headers_mp, data, is_json=False
            )
        except Exception as err:
            self._error(f"Exception sending event: {str(err)}")
            return None

        logger.debug("Got status code %d when sending events", response.status_code)

        if response.status_code == 200:
            return response.json()

        self._error(f"Got status code {response.status_code} when sending events")
        return None

    @skip_if_failed("_aborted", "_suppress_errors", None)
    def send_heartbeat(self) -> dict[str, typing.Any] | None:
        """
        Send heartbeat
        """
        logger.debug("Sending heartbeat")

        try:
            response = put(
                f"{self._url}/api/runs/heartbeat", self._headers, {"id": self._id}
            )
        except Exception as err:
            self._error(f"Exception creating run: {str(err)}")
            return None

        logger.debug("Got status code %d when sending heartbeat", response.status_code)

        if response.status_code == 200:
            return response.json()

        self._error(f"Got status code {response.status_code} when sending heartbeat")
        return None

    @skip_if_failed("_aborted", "_suppress_errors", False)
    def check_token(self) -> bool:
        """
        Check token
        """
        if time.time() - get_expiry(self._token) > 0:
            self._error("Token has expired")
            return False
        return True