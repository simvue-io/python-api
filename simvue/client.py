from concurrent.futures import ProcessPoolExecutor
import json
import os
import typing
import logging
import requests

try:
    import matplotlib as plt
except ImportError:
    plt = None

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame

from .serialization import deserialize
from .utilities import get_auth, get_server_version, check_extra
from .converters import to_dataframe, metric_set_dataframe, metric_to_dataframe

CONCURRENT_DOWNLOADS = 10
DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_TIMEOUT = 30

logger = logging.getLogger(__name__)


def downloader(job: dict[str, typing.Any]) -> bool:
    """
    Download the specified file to the specified directory
    """
    try:
        response = requests.get(job["url"], stream=True, timeout=DOWNLOAD_TIMEOUT)
    except requests.exceptions.RequestException:
        return False

    total_length = response.headers.get("content-length")

    with open(os.path.join(job["path"], job["filename"]), "wb") as fh:
        if total_length is None:
            fh.write(response.content)
        else:
            for data in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                fh.write(data)

    return True


class Client:
    """
    Class for querying Simvue
    """

    def __init__(self) -> None:
        self._url, self._token = get_auth()

        if not self._url:
            raise AssertionError("Failed to retrieve URL from configuration")

        self._headers: dict[str, str] = {"Authorization": f"Bearer {self._token}"}
        self._version: int | None = get_server_version()

    def get_run(self, run: int) -> dict[str, typing.Any] | None:
        """
        Get a single run
        """
        response = requests.get(f"{self._url}/api/runs/{run}", headers=self._headers)

        if response.status_code != 200:
            raise AssertionError(
                f"Request for run {run} failed with: {response.json().get('detail', 'Request failed')}"
            )

        return response.json()

    def get_runs(
        self, filters: list[str], system=False, metadata=False, format="dict"
    ) -> typing.Union[dict[str, typing.Any], None, "DataFrame"]:
        """
        Get runs
        """
        params = {
            "name": None,
            "filters": json.dumps(filters),
            "return_basic": True,
            "return_system": system,
            "return_metadata": metadata,
        }

        response = requests.get(
            f"{self._url}/api/runs", headers=self._headers, params=params
        )
        response.raise_for_status()

        if response.status_code == 200:
            if format == "dict":
                return response.json()["data"]
            elif format == "dataframe":
                return to_dataframe(response.json())
            else:
                raise AssertionError("invalid format specified")

        return None

    def delete_run(self, run: int) -> dict[str, typing.Any] | None:
        """
        Delete run
        """
        params = {"run_id": run}

        response = requests.delete(
            f"{self._url}/api/runs", headers=self._headers, params=params
        )

        if response.status_code == 200 and (_runs := response.json().get("runs")):
            return _runs

        raise AssertionError(response.text)

    def _get_folder_id_from_path(self, path: str) -> str | None:
        """
        Get folder id for the specified path
        """
        params = {"filters": json.dumps([f"path == {path}"])}

        response = requests.get(
            f"{self._url}/api/folders", headers=self._headers, params=params
        )

        if all(
            [
                response.status_code == 200,
                len(_data := response.json().get("data", [])) > 0,
                _id := _data[0].get("id"),
            ]
        ):
            return _id

        return None

    def delete_runs(self, folder: str) -> dict[str, typing.Any] | None:
        """
        Delete runs in folder
        """
        if not (folder_id := self._get_folder_id_from_path(folder)):
            logger.info(f"No match for folder '{folder}' nothing to be deleted.")
            return None

        params: dict[str, bool] = {"runs_only": True, "runs": True}

        response = requests.delete(
            f"{self._url}/api/folders/{folder_id}", headers=self._headers, params=params
        )

        if response.status_code == 200 and (_runs := response.json().get("runs")):
            return _runs

        raise AssertionError(response.text)

    def delete_folder(
        self, folder: str, runs: bool = False
    ) -> dict[str, typing.Any] | None:
        """
        Delete folder
        """
        if not (folder_id := self._get_folder_id_from_path(folder)):
            return None

        params: dict[str, bool] = {"runs": True} if runs else {}

        response = requests.delete(
            f"{self._url}/api/folders/{folder_id}", headers=self._headers, params=params
        )

        if response.status_code == 200 and (_runs := response.json().get("runs")):
            return _runs

        raise AssertionError(response.text)

    def list_artifacts(self, run, category=None) -> dict[str, typing.Any] | None:
        """
        List artifacts associated with a run
        """
        params: dict[str,] = {"run": run}
        if category:
            params["category"] = category

        response = requests.get(
            f"{self._url}/api/artifacts", headers=self._headers, params=params
        )

        if (
            response.status_code == 404
            and response.json().get("detail") == "run does not exist"
        ):
            raise AssertionError("Run does not exist")

        if response.status_code == 200:
            return response.json()

        raise AssertionError(response.text)

    def get_artifact(self, run: int, name: str, allow_pickle: bool = False):
        """
        Return the contents of the specified artifact
        """
        params: dict[str, int | str] = {"run_id": run, "name": name}

        response = requests.get(
            f"{self._url}/api/runs/{run}/artifacts",
            headers=self._headers,
            params=params,
        )

        if response.status_code == 404 and (_detail := response.json().get("detail")):
            if _detail == "No such run":
                raise RuntimeError("Run does not exist")
            elif _detail == "artifact does not exist":
                raise RuntimeError("Artifact does not exist")

        if response.status_code != 200:
            return None

        _json_response: dict = response.json()

        url = _json_response[0]["url"]
        mimetype = _json_response[0]["type"]

        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
        response.raise_for_status()

        content = deserialize(response.content, mimetype, allow_pickle)
        if content is not None:
            return content

        return response.content

    def get_artifact_as_file(self, run, name, path="./"):
        """
        Download an artifact
        """
        params = {"run_id": run, "name": name}

        response = requests.get(
            f"{self._url}/api/runs/{run}/artifacts",
            headers=self._headers,
            params=params,
        )

        if response.status_code == 404:
            if "detail" in response.json():
                if response.json()["detail"] == "run does not exist":
                    raise RuntimeError("Run does not exist")
                elif response.json()["detail"] == "artifact does not exist":
                    raise RuntimeError("Artifact does not exist")

        if response.status_code == 200:
            if response.json():
                url = response.json()[0]["url"]
                if not downloader(
                    {"url": url, "filename": os.path.basename(name), "path": path}
                ):
                    raise RuntimeError("Failed to download file data")

        else:
            raise requests.RequestException(
                f"Retrieval of artifacts for run '{run}' failed with: {response.json()['detail']}"
            )

    def get_artifacts_as_files(
        self,
        run,
        path=None,
        category=None,
        startswith=None,
        contains=None,
        endswith=None,
    ):
        """
        Get artifacts associated with a run & save as files
        """
        params = {}
        params["category"] = category

        response = requests.get(
            f"{self._url}/api/runs/{run}/artifacts",
            headers=self._headers,
            params=params,
        )

        if response.status_code == 404:
            if "detail" in response.json():
                if response.json()["detail"] == "run does not exist":
                    raise RuntimeError("Run does not exist")

        if not path:
            path = "./"

        if response.status_code == 200:
            downloads = []
            for item in response.json():
                if startswith:
                    if not item["name"].startswith(startswith):
                        continue
                if contains:
                    if contains not in item["name"]:
                        continue
                if endswith:
                    if not item["name"].endswith(endswith):
                        continue

                job = {}
                job["url"] = item["url"]
                job["filename"] = os.path.basename(item["name"])
                job["path"] = os.path.join(path, os.path.dirname(item["name"]))

                if os.path.isfile(os.path.join(job["path"], job["filename"])):
                    continue

                if job["path"]:
                    os.makedirs(job["path"], exist_ok=True)
                else:
                    job["path"] = path
                downloads.append(job)

            with ProcessPoolExecutor(CONCURRENT_DOWNLOADS) as executor:
                for item in downloads:
                    executor.submit(downloader, item)

        else:
            raise RuntimeError(response.text)

    def get_folder(self, folder, tags=False, metadata=False):
        """
        Get a single folder
        """
        params = {"filters": json.dumps([f"path == {folder}"])}

        response = requests.get(
            f"{self._url}/api/folders", headers=self._headers, params=params
        )

        if response.status_code == 404:
            if "detail" in response.json():
                if response.json()["detail"] == "no such folder":
                    raise RuntimeError("Folder does not exist")

        if response.status_code == 200:
            if len(response.json()["data"]) == 0:
                raise RuntimeError("Folder does not exist")

            return response.json()["data"][0]

        raise RuntimeError(response.text)

    def get_folders(self, filters, tags=False, metadata=False):
        """
        Get folders
        """
        params = {"filters": json.dumps(filters)}

        response = requests.get(
            f"{self._url}/api/folders", headers=self._headers, params=params
        )

        if response.status_code == 200:
            return response.json()["data"]

        raise RuntimeError(response.text)

    def get_metrics_names(self, run):
        """
        Return a list of metrics names
        """
        params = {"runs": json.dumps([run])}

        response = requests.get(
            f"{self._url}/api/metrics/names", headers=self._headers, params=params
        )

        if response.status_code == 200:
            return response.json()

        raise RuntimeError(response.text)

    def get_metrics_summaries(self, run, name):
        """
        Get summary metrics for the specified run and metrics name
        """
        params = {"runs": run, "metrics": name, "summary": True}

        response = requests.get(
            f"{self._url}/api/metrics", headers=self._headers, params=params
        )

        if response.status_code == 200:
            return response.json()

        raise RuntimeError(response.text)

    def get_metrics(
        self,
        run: str,
        name: str,
        xaxis: typing.Union[typing.Literal["step"], typing.Literal["time"]],
        max_points: int = -1,
        format: typing.Union[
            typing.Literal["list"], typing.Literal["dataframe"]
        ] = "list",
    ):
        """
        Get time series metrics for the specified run and metrics name
        """
        logger.debug(f"Sending request: {self._url}/api/runs/{run}")
        response_run = requests.get(f"{self._url}/api/runs/{run}", headers=self._headers)

        if response_run.status_code == 404:
            raise AssertionError(f"Run with ID '{run}' does not exist")

        if response_run.status_code != 200:
            raise requests.HTTPError(f"{response_run.status_code}: {response_run.text}")

        run_name = response_run.json().get("name")

        params = {
            "runs": f'["{run}"]',
            "metrics": f'["{name}"]',
            "xaxis": xaxis,
            "max_points": max_points,
        }

        if xaxis not in ("step", "time", "timestamp"):
            raise AssertionError(
                'Invalid xaxis specified, should be either "step", "time", or "timestamp"'
            )

        if format not in ("list", "dataframe"):
            raise AssertionError(
                'Invalid format specified, should be either "list" or "dataframe"'
            )
        
        # FIXME: Server rejects lists in usual form so have to create URL manually
        _url: str = f"{self._url}/api/metrics?{'&'.join(a+'='+str(b) for a, b in params.items())}"

        logger.debug(
            f"Sending request: {_url}"
        )

        response_metrics = requests.get(
            f"{self._url}/api/metrics",
            params=params,
            headers=self._headers
        )

        if response_metrics.status_code == 404:
            raise AssertionError(
                f"Metric '{name}' not found for run '{run}: {run_name}'"
            )

        if response_metrics.status_code != 200:
            raise requests.HTTPError(f"{response_metrics.status_code}: {response_metrics.text}")

        _json_data: dict = response_metrics.json()

        if not _json_data:
            raise AssertionError(
                f"No results found for metric '{name}' in run '{run}: {run_name}'"
            )

        data: list[int | float] = []

        if (_items := _json_data.get(name)) is None:
            raise KeyError(
                f"Failed to retrieve metric '{name}' from run '{run}: {run_name}'"
            )
        for item in _items:
            data.append([item[xaxis], item["value"], run_name, name])

        if format == "dataframe":
            return metric_to_dataframe(data, xaxis, name=name)

        return data

    def get_metrics_multiple(
        self, runs, names, xaxis, max_points=0, aggregate=False, format="list"
    ):
        """
        Get time series metrics from multiple runs and/or metrics
        """
        params = {
            "runs": json.dumps(runs),
            "metrics": json.dumps(names),
            "aggregate": aggregate,
            "max_points": max_points,
            "xaxis": xaxis,
        }

        if xaxis not in ("step", "time"):
            raise ValueError(
                'Invalid xaxis specified, should be either "step" or "time"'
            )

        if format not in ("list", "dataframe"):
            raise ValueError(
                'Invalid format specified, should be either "list" or "dataframe"'
            )

        response = requests.get(
            f"{self._url}/api/metrics", headers=self._headers, params=params
        )

        if response.status_code == 200:
            data = []
            if not aggregate:
                for run in response.json():
                    for name in response.json()[run]:
                        for item in response.json()[run][name]:
                            data.append([item[xaxis], item["value"], run, name])
            else:
                for name in response.json():
                    for item in response.json()[name]:
                        data.append(
                            [
                                item[xaxis],
                                item["min"],
                                item["average"],
                                item["max"],
                                name,
                            ]
                        )

            if format == "dataframe":
                return metric_set_dataframe(response.json(), xaxis)
            return data

        raise RuntimeError(response.text)

    @check_extra("plot")
    def plot_metrics(self, runs, names, xaxis, max_points=0):
        """
        Plot time series metrics from multiple runs and/or metrics
        """
        if not isinstance(runs, list):
            raise ValueError("Invalid runs specified, must be a list of run names.")

        if not isinstance(names, list):
            raise ValueError("Invalid names specified, must be a list of metric names.")

        data = self.get_metrics_multiple(
            runs, names, xaxis, max_points, format="dataframe"
        )

        for run in runs:
            for name in names:
                label = None
                if len(runs) > 1 and len(names) > 1:
                    label = f"{run}: {name}"
                elif len(runs) > 1 and len(names) == 1:
                    label = run
                elif len(runs) == 1 and len(names) > 1:
                    label = name

                plt.plot(
                    data[(run, name, xaxis)], data[(run, name, "value")], label=label
                )

        if xaxis == "step":
            plt.xlabel("steps")
        elif xaxis == "time":
            plt.xlabel("relative time")

        if len(names) == 1:
            plt.ylabel(names[0])

        return plt

    def get_events(self, run, filter=None, start=0, num=0):
        """
        Return events from the specified run
        """
        params = {"run": run, "filter": filter, "start": start, "num": num}

        response = requests.get(
            f"{self._url}/api/events", headers=self._headers, params=params
        )

        if response.status_code == 200:
            return response.json()["data"]

        raise RuntimeError(response.text)
