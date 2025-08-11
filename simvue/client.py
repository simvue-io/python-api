"""
Simvue Client
=============

Contains a Simvue client class for interacting with existing objects on the
server including deletion and retrieval.
"""

import contextlib
import json
import logging
import pathlib
import typing
import http
import pydantic
from concurrent.futures import ThreadPoolExecutor, as_completed
from pandas import DataFrame

import requests

from simvue.api.objects.alert.base import AlertBase
from simvue.exception import ObjectNotFoundError

from .converters import (
    aggregated_metrics_to_dataframe,
    to_dataframe,
    parse_run_set_metrics,
)
from .serialization import deserialize_data
from .simvue_types import DeserializedContent
from .utilities import check_extra, prettify_pydantic
from .models import FOLDER_REGEX, NAME_REGEX
from .config.user import SimvueConfiguration
from .api.request import get_json_from_response
from .api.objects import (
    Run,
    Folder,
    Tag,
    Artifact,
    Alert,
    FileArtifact,
    ObjectArtifact,
    get_folder_from_path,
)


CONCURRENT_DOWNLOADS = 10
DOWNLOAD_CHUNK_SIZE = 8192

logger = logging.getLogger(__file__)


def _download_artifact_to_file(
    artifact: FileArtifact | ObjectArtifact, output_dir: pathlib.Path | None
) -> None:
    if not artifact.name:
        raise RuntimeError(f"Expected artifact '{artifact.id}' to have a name")
    _output_file = (output_dir or pathlib.Path.cwd()).joinpath(artifact.name)
    # If this is a hierarchical structure being downloaded, need to create directories
    _output_file.parent.mkdir(parents=True, exist_ok=True)
    with _output_file.open("wb") as out_f:
        for content in artifact.download_content():
            out_f.write(content)


class Client:
    """Class for querying a Simvue server instance."""

    def __init__(
        self,
        *,
        server_token: pydantic.SecretStr | None = None,
        server_url: str | None = None,
    ) -> None:
        """Initialise an instance of the Simvue client

        Parameters
        ----------
        server_token : str, optional
            specify token, if unset this is read from the config file
        server_url : str, optional
            specify URL, if unset this is read from the config file
        """
        self._user_config = SimvueConfiguration.fetch(
            server_token=server_token, server_url=server_url, mode="online"
        )

        for label, value in zip(
            ("URL", "API token"),
            (self._user_config.server.url, self._user_config.server.url),
        ):
            if not value:
                logger.warning(f"No {label} specified")

        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {self._user_config.server.token.get_secret_value()}",
            "Accept-Encoding": "gzip",
        }

    @prettify_pydantic
    @pydantic.validate_call
    def get_run_id_from_name(
        self, name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
    ) -> str:
        """Get Run ID from the server matching the specified name

        Assumes a unique name for this run. If multiple results are found this
        method will fail.

        Parameters
        ----------
        name : str
            the name of the run

        Returns
        -------
        str
            the unique identifier for this run

        Raises
        ------
        RuntimeError
            if either information could not be retrieved from the server,
            or multiple/no runs are found
        """
        _runs = Run.get(filters=json.dumps([f"name == {name}"]))

        try:
            _id, _ = next(_runs)
        except StopIteration as e:
            raise RuntimeError(
                "Could not collect ID - no run found with this name."
            ) from e

        with contextlib.suppress(StopIteration):
            next(_runs)
            raise RuntimeError(
                "Could not collect ID - more than one run exists with this name."
            )

        return _id

    @prettify_pydantic
    @pydantic.validate_call
    def get_run(self, run_id: str) -> Run | None:
        """Retrieve a single run

        Parameters
        ----------
        run_id : str
            the unique identifier for this run

        Returns
        -------
        dict[str, Any]
            response containing information on the given run

        Raises
        ------
        RuntimeError
            if retrieval of information from the server on this run failed
        """
        return Run(identifier=run_id, read_only=True)

    @prettify_pydantic
    @pydantic.validate_call
    def get_run_name_from_id(self, run_id: str) -> str:
        """Retrieve the name of a run from its identifier

        Parameters
        ----------
        run_id : str
            the unique identifier for the run

        Returns
        -------
        str
            the registered name for the run
        """
        return Run(identifier=run_id).name

    @prettify_pydantic
    @pydantic.validate_call
    def get_runs(
        self,
        filters: list[str] | None,
        *,
        system: bool = False,
        metrics: bool = False,
        alerts: bool = False,
        metadata: bool = False,
        output_format: typing.Literal["dict", "objects", "dataframe"] = "objects",
        count_limit: pydantic.PositiveInt | None = 100,
        start_index: pydantic.NonNegativeInt = 0,
        show_shared: bool = True,
        sort_by_columns: list[tuple[str, bool]] | None = None,
    ) -> DataFrame | typing.Generator[tuple[str, Run], None, None] | None:
        """Retrieve all runs matching filters.

        Parameters
        ----------
        filters: list[str] | None
            set of filters to apply to query results. If None is specified
            return all results without filtering.
        metadata : bool, optional
            whether to include metadata information in the response.
            Default False.
        metrics : bool, optional
            whether to include metrics information in the response.
            Default False.
        alerts : bool, optional
            whether to include alert information in the response.
            Default False.
        output_format : Literal['dict', objects', 'dataframe'], optional
            the structure of the response
                * dict - dictionary of values.
                * objects - a dictionary of objects (default).
                * dataframe - a dataframe (Pandas must be installed).
        count_limit : int, optional
            maximum number of entries to return. Default is 100.
        start_index : int, optional
            the index from which to count entries. Default is 0.
        show_shared : bool, optional
            whether to include runs shared with the current user. Default is True.
        sort_by_columns : list[tuple[str, bool]], optional
            sort by columns in the order given,
            list of tuples in the form (column_name: str, sort_descending: bool),
            default is None.

        Returns
        -------
        pandas.DataFrame | Generator[tuple[str, Run], None, None]
            either the JSON response from the runs request or the results in the
            form of a Pandas DataFrame

        Yields
        ------
        tuple[str, Run]
            identifier and Run object

        Raises
        ------
        ValueError
            if a value outside of 'dict' or 'dataframe' is specified
        RuntimeError
            if there was a failure in data retrieval from the server
        """
        filters = filters or []
        if not show_shared:
            filters += ["user == self"]

        _runs = Run.get(
            count=count_limit,
            offset=start_index,
            filters=json.dumps(filters),
            return_basic=True,
            return_metrics=metrics,
            return_alerts=alerts,
            return_system=system,
            return_metadata=metadata,
            sorting=[dict(zip(("column", "descending"), a)) for a in sort_by_columns]
            if sort_by_columns
            else None,
        )

        if output_format == "objects":
            return _runs

        _params: dict[str, bool | str] = {
            "filters": json.dumps(filters),
            "return_basic": True,
            "return_metrics": metrics,
            "return_alerts": alerts,
            "return_system": system,
            "return_metadata": metadata,
        }

        response = requests.get(
            f"{self._user_config.server.url}/runs",
            headers=self._headers,
            params=_params,
        )

        response.raise_for_status()

        if output_format not in ("dict", "dataframe"):
            raise ValueError("Invalid format specified")

        json_response = get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario="Run retrieval",
            response=response,
        )

        if (response_data := json_response.get("data")) is None:
            raise RuntimeError("Failed to retrieve runs data")

        if output_format == "dict":
            return response_data

        return to_dataframe(response_data)

    @prettify_pydantic
    @pydantic.validate_call
    def delete_run(self, run_id: str) -> dict | None:
        """Delete run by identifier

        Parameters
        ----------
        run_id : str
            the unique identifier for the run

        Returns
        -------
        dict | None
            the request response after deletion

        Raises
        ------
        RuntimeError
            if the deletion failed due to server request error
        """
        return Run(identifier=run_id).delete() or None

    def _get_folder_from_path(self, path: str) -> Folder | None:
        """Retrieve folder for the specified path if found

        Parameters
        ----------
        path : str
            the path to search for

        Returns
        -------
        Folder | None
            if a match is found, return the folder
        """
        _folders = Folder.get(filters=json.dumps([f"path == {path}"]))

        try:
            _, _folder = next(_folders)
            return _folder  # type: ignore
        except StopIteration:
            return None

    def _get_folder_id_from_path(self, path: str) -> str | None:
        """Retrieve folder identifier for the specified path if found

        Parameters
        ----------
        path : str
            the path to search for

        Returns
        -------
        str | None
            if a match is found, return the identifier of the folder
        """
        _ids = Folder.ids(filters=json.dumps([f"path == {path}"]))

        try:
            _id = next(_ids)
        except StopIteration:
            return None

        with contextlib.suppress(StopIteration):
            next(_ids)
            raise RuntimeError(
                f"Expected single folder match for '{path}', but found duplicate."
            )

        return _id

    @prettify_pydantic
    @pydantic.validate_call
    def delete_runs(
        self, folder_path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)]
    ) -> list | None:
        """Delete runs in a named folder

        Parameters
        ----------
        folder_path : str
            the path of the folder on which to perform deletion. All folder
            paths are prefixed with `/`

        Returns
        -------
        list | None
            List of deleted runs

        Raises
        ------
        RuntimeError
            if deletion fails due to server request error
        """
        if not (_folder := self._get_folder_from_path(folder_path)):
            raise ValueError(f"Could not find a folder matching '{folder_path}'")
        _delete = _folder.delete(runs_only=True, delete_runs=True, recursive=False)
        return _delete.get("runs", [])

    @prettify_pydantic
    @pydantic.validate_call
    def delete_folder(
        self,
        folder_path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
        recursive: bool = False,
        remove_runs: bool = False,
        allow_missing: bool = False,
    ) -> list | None:
        """Delete a folder by name

        Parameters
        ----------
        folder_path : str
            name of the folder to delete. All paths are prefixed with `/`
        recursive : bool, optional
            if folder contains additional folders remove these, else return an
            error. Default False.
        remove_runs : bool, optional
            whether to delete runs associated with this folder, by default False
        allow_missing : bool, optional
            allows deletion of folders which do not exist, else raise exception,
            default is exception raise

        Returns
        -------
        list | None
            if a folder is identified the runs also removed during execution

        Raises
        ------
        RuntimeError
            if deletion of the folder from the server failed
        """
        folder_id = self._get_folder_id_from_path(folder_path)

        if not folder_id:
            if allow_missing:
                return None
            else:
                raise ObjectNotFoundError(
                    name=folder_path,
                    obj_type="folder",
                )
        _response = Folder(identifier=folder_id).delete(
            delete_runs=remove_runs, recursive=recursive, runs_only=False
        )

        if folder_id not in _response.get("folders", []):
            raise RuntimeError("Deletion of folder failed, server returned mismatch.")

        return _response.get("runs", [])

    @prettify_pydantic
    @pydantic.validate_call
    def delete_alert(self, alert_id: str) -> None:
        """Delete an alert from the server by ID

        Parameters
        ----------
        alert_id : str
            the unique identifier for the alert
        """
        Alert(identifier=alert_id).delete()  # type: ignore

    @prettify_pydantic
    @pydantic.validate_call
    def list_artifacts(
        self, run_id: str, sort_by_columns: list[tuple[str, bool]] | None = None
    ) -> typing.Generator[Artifact, None, None]:
        """Retrieve artifacts for a given run

        Parameters
        ----------
        run_id : str
            unique identifier for the run
        sort_by_columns : list[tuple[str, bool]], optional
            sort by columns in the order given,
            list of tuples in the form (column_name: str, sort_descending: bool),
            default is None.

        Yields
        ------
        str, Artifact
            ID and artifact entry for relevant artifacts

        Raises
        ------
        RuntimeError
            if retrieval of artifacts failed when communicating with the server
        """
        return Artifact.get(
            runs=json.dumps([run_id]),
            sorting=[dict(zip(("column", "descending"), a)) for a in sort_by_columns]
            if sort_by_columns
            else None,
        )  # type: ignore

    def _retrieve_artifacts_from_server(
        self, run_id: str, name: str
    ) -> FileArtifact | ObjectArtifact | None:
        return Artifact.from_name(
            run_id=run_id,
            name=name,
            server_url=self._user_config.server.url,
            server_token=self._user_config.server.token,
        )

    @prettify_pydantic
    @pydantic.validate_call
    def abort_run(self, run_id: str, reason: str) -> dict | list:
        """Abort a currently active run on the server

        Parameters
        ----------
        run_id : str
            the unique identifier for the run
        reason : str
            reason for abort

        Returns
        -------
        dict | list
            response from server
        """
        return Run(identifier=run_id).abort(reason=reason)

    @prettify_pydantic
    @pydantic.validate_call
    def get_artifact(
        self, run_id: str, name: str, allow_pickle: bool = False
    ) -> typing.Any:
        """Return the contents of a specified artifact

        Parameters
        ----------
        run_id : str
            the unique identifier of the run from which to retrieve the artifact
        name : str
            the name of the artifact to retrieve
        allow_pickle : bool, optional
            whether to de-pickle the retrieved data, by default False

        Returns
        -------
        DataFrame | Figure | FigureWidget | ndarray | Buffer | Tensor | bytes
            de-serialized content of artifact if retrieved, else content
            of the server response

        Raises
        ------
        RuntimeError
            if retrieval of artifact from the server failed
        """
        _artifact = self._retrieve_artifacts_from_server(run_id, name)

        if not _artifact:
            raise ObjectNotFoundError(
                obj_type="artifact",
                name=name,
                extra=f"for run '{run_id}'",
            )

        _content = b"".join(_artifact.download_content())

        _deserialized_content: DeserializedContent | None = deserialize_data(
            _content, _artifact.mime_type, allow_pickle
        )

        # Numpy array return means just 'if content' will be ambiguous
        # so must explicitly check if None
        return _content if _deserialized_content is None else _deserialized_content

    @prettify_pydantic
    @pydantic.validate_call
    def get_artifact_as_file(
        self,
        run_id: str,
        name: str,
        output_dir: pydantic.DirectoryPath | None = None,
    ) -> None:
        """Retrieve the specified artifact in the form of a file

        Information is saved to a file as opposed to deserialized

        Parameters
        ----------
        run_id : str
            unique identifier for the run to be queried
        name : str
            the name of the artifact to be retrieved
        output_dir: str | None, optional
            path to download retrieved content to, the default of None
            uses the current working directory.

        Raises
        ------
        RuntimeError
            if there was a failure during retrieval of information from the
            server
        """
        _artifact = self._retrieve_artifacts_from_server(run_id, name)

        if not _artifact:
            raise ObjectNotFoundError(
                obj_type="artifact",
                name=name,
                extra=f"for run '{run_id}'",
            )

        _download_artifact_to_file(_artifact, output_dir)

    @prettify_pydantic
    @pydantic.validate_call
    def get_artifacts_as_files(
        self,
        run_id: str,
        category: typing.Literal["input", "output", "code"] | None = None,
        output_dir: pydantic.DirectoryPath | None = None,
    ) -> None:
        """Retrieve artifacts from the given run as a set of files

        Parameters
        ----------
        run_id : str
            the unique identifier for the run
        category : Literal['input', 'output', 'code']
            category of file to retrieve, default of None returns all
                * input - this file is an input file.
                * output - this file is created by the run.
                * code - this file represents an executed script
        output_dir : str | None, optTODOional
            location to download files to, the default of None will download
            them to the current working directory

        Raises
        ------
        RuntimeError
            if there was a failure retrieving artifacts from the server
        """
        _artifacts: typing.Generator[tuple[str, Artifact], None, None] = (
            Artifact.from_run(run_id=run_id, category=category)
        )

        with ThreadPoolExecutor(
            CONCURRENT_DOWNLOADS, thread_name_prefix=f"get_artifacts_run_{run_id}"
        ) as executor:
            futures = [
                executor.submit(_download_artifact_to_file, artifact, output_dir)
                for _, artifact in _artifacts
            ]
            for future, (_, artifact) in zip(as_completed(futures), _artifacts):
                try:
                    future.result()
                except Exception as e:
                    raise RuntimeError(
                        f"Download of file {artifact.storage_url} "
                        f"failed with exception: {e}"
                    ) from e

    @prettify_pydantic
    @pydantic.validate_call
    def get_folder(
        self,
        folder_path: typing.Annotated[str, pydantic.Field(pattern=FOLDER_REGEX)],
        read_only: bool = True,
    ) -> Folder | None:
        """Retrieve a folder by identifier

        Parameters
        ----------
        folder_path : str
            the path of the folder to retrieve on the server.
            Paths are prefixed with `/`
        read_only : bool, optional
            whether the returned object should be editable or not,
            default is True, the object is a cached copy of data
            from the server.

        Returns
        -------
        Folder | None
            data for the requested folder if it exists else None

        Raises
        ------
        RuntimeError
            if there was a failure when retrieving information from the server
        """
        try:
            _folder = get_folder_from_path(path=folder_path)
        except ObjectNotFoundError:
            return None
        _folder.read_only(is_read_only=read_only)
        return _folder

    @pydantic.validate_call
    def get_folders(
        self,
        *,
        filters: list[str] | None = None,
        count: pydantic.PositiveInt = 100,
        start_index: pydantic.NonNegativeInt = 0,
        sort_by_columns: list[tuple[str, bool]] | None = None,
    ) -> typing.Generator[tuple[str, Folder], None, None]:
        """Retrieve folders from the server

        Parameters
        ----------
        filters : list[str] | None
            set of filters to apply to the search
        count : int, optional
            maximum number of entries to return. Default is 100.
        start_index : int, optional
            the index from which to count entries. Default is 0.
        sort_by_columns : list[tuple[str, bool]], optional
            sort by columns in the order given,
            list of tuples in the form (column_name: str, sort_descending: bool),
            default is None.

        Returns
        -------
        Generator[str, Folder]
            all data for folders matching the filter request in form (id, Folder)

        Raises
        ------
        RuntimeError
            if there was a failure retrieving data from the server
        """
        return Folder.get(
            filters=json.dumps(filters or []),
            count=count,
            offset=start_index,
            sorting=[dict(zip(("column", "descending"), a)) for a in sort_by_columns]
            if sort_by_columns
            else None,
        )  # type: ignore

    @prettify_pydantic
    @pydantic.validate_call
    def get_metrics_names(self, run_id: str) -> typing.Generator[str, None, None]:
        """Return information on all metrics within a run

        Parameters
        ----------
        run_id : str
            unique identifier of the run

        Returns
        -------
        Generator[str, None, None]
            names of metrics in the given run

        Raises
        ------
        RuntimeError
            if there was a failure retrieving information from the server
        """
        _run = Run(identifier=run_id)

        for id, _ in _run.metrics:
            yield id

    def _get_run_metrics_from_server(
        self,
        metric_names: list[str],
        run_ids: list[str],
        xaxis: str,
        aggregate: bool,
        max_points: int | None = None,
    ) -> dict[str, typing.Any]:
        params: dict[str, str | int | None] = {
            "runs": json.dumps(run_ids),
            "aggregate": aggregate,
            "metrics": json.dumps(metric_names),
            "xaxis": xaxis,
            "max_points": max_points,
        }

        metrics_response: requests.Response = requests.get(
            f"{self._user_config.server.url}/metrics",
            headers=self._headers,
            params=params,
        )

        return get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of metrics '{metric_names}' in runs '{run_ids}'",
            response=metrics_response,
        )

    @prettify_pydantic
    @pydantic.validate_call
    def get_metric_values(
        self,
        metric_names: list[str],
        xaxis: typing.Literal["step", "time", "timestamp"],
        *,
        output_format: typing.Literal["dataframe", "dict"] = "dict",
        run_ids: list[str] | None = None,
        run_filters: list[str] | None = None,
        use_run_names: bool = False,
        aggregate: bool = False,
        max_points: pydantic.PositiveInt | None = None,
    ) -> dict | DataFrame | None:
        """Retrieve the values for a given metric across multiple runs

        Uses filters to specify which runs should be retrieved.

        NOTE if the number of runs exceeds 100 'aggregated' will be set to True,
        and aggregated is not supported for the 'timestamp' xaxis format

        Parameters
        ----------
        metric_names : list[str]
            the names of metrics to return values for
        xaxis : Literal["step", "time", "timestamp"]
            the x-axis type
                * step - enumeration.
                * time - time in seconds.
                * timestamp - time stamp.
        output_format : Literal['dataframe', 'dict']
            the format of the output
                * dict - python dictionary of values (default).
                * dataframe - values as dataframe (requires Pandas).
        run_ids : list[str], optional
            list of runs by id to include within metric retrieval
        run_filters : list[str]
            filters for specifying runs to include
        use_run_names : bool, optional
            use run names as opposed to IDs, note this is not recommended for
            multiple runs with the same name. Default is False.
        aggregate : bool, optional
            return results as averages (not compatible with xaxis=timestamp),
            default is False
        max_points : int, optional
            maximum number of data points, by default None (all)

        Returns
        -------
        dict or DataFrame or None
            values for the given metric at each time interval
            if no runs pass filtering then return None
        """
        if not metric_names:
            raise ValueError("No metric names were provided")

        if run_filters and run_ids:
            raise AssertionError(
                "Specification of both 'run_ids' and 'run_filters' "
                "in get_metric_values is ambiguous"
            )

        if xaxis == "timestamp" and aggregate:
            raise AssertionError(
                "Cannot return metric values with options 'aggregate=True' and "
                "'xaxis=timestamp'"
            )

        _args = {"filters": json.dumps(run_filters)} if run_filters else {}

        if not run_ids:
            _run_data = dict(Run.get(**_args))

        if not (
            _run_metrics := self._get_run_metrics_from_server(
                metric_names=metric_names,
                run_ids=run_ids or list(_run_data.keys()),
                xaxis=xaxis,
                aggregate=aggregate,
                max_points=max_points,
            )
        ):
            return None
        if aggregate:
            return aggregated_metrics_to_dataframe(
                _run_metrics, xaxis=xaxis, parse_to=output_format
            )
        if use_run_names:
            _run_metrics = {
                Run(identifier=key).name: _run_metrics[key]
                for key in _run_metrics.keys()
            }
        return parse_run_set_metrics(
            _run_metrics,
            xaxis=xaxis,
            run_labels=list(_run_metrics.keys()),
            parse_to=output_format,
        )

    @check_extra("plot")
    @prettify_pydantic
    @pydantic.validate_call
    def plot_metrics(
        self,
        run_ids: list[str],
        metric_names: list[str],
        xaxis: typing.Literal["step", "time"],
        *,
        max_points: int | None = None,
    ) -> typing.Any:
        """Plt the time series values for multiple metrics/runs

        Parameters
        ----------
        run_ids : list[str]
            unique identifiers for runs to plot
        metric_names : list[str]
            names of metrics to plot
        xaxis : str, ('step' | 'time' | 'timestep')
            the x axis to plot against
        max_points : int, optional
            maximum number of data points, by default None (all)

        Returns
        -------
        Figure
            plot figure object

        Raises
        ------
        ValueError
            if invalid arguments are provided
        """
        if not isinstance(run_ids, list):
            raise ValueError("Invalid runs specified, must be a list of run names.")

        if not isinstance(metric_names, list):
            raise ValueError("Invalid names specified, must be a list of metric names.")

        data: DataFrame = self.get_metric_values(  # type: ignore
            run_ids=run_ids,
            metric_names=metric_names,
            xaxis=xaxis,
            max_points=max_points,
            output_format="dataframe",
            aggregate=False,
        )

        if data is None:
            raise RuntimeError(
                f"Cannot plot metrics {metric_names}, no data found for runs {run_ids}."
            )

        # Undo multi-indexing
        flattened_df = data.reset_index()

        import matplotlib.pyplot as plt

        for run in run_ids:
            for name in metric_names:
                label = None
                if len(run_ids) > 1 and len(metric_names) > 1:
                    label = f"{run}: {name}"
                elif len(run_ids) > 1 and len(metric_names) == 1:
                    label = run
                elif len(run_ids) == 1 and len(metric_names) > 1:
                    label = name

                flattened_df.plot(y=name, x=xaxis, label=label)

        if xaxis == "step":
            plt.xlabel("Steps")
        elif xaxis == "time":
            plt.xlabel("Relative Time")
        if xaxis == "step":
            plt.xlabel("steps")
        elif xaxis == "timestamp":
            plt.xlabel("Time")

        if len(metric_names) == 1:
            plt.ylabel(metric_names[0])

        return plt.figure()

    @prettify_pydantic
    @pydantic.validate_call
    def get_events(
        self,
        run_id: str,
        *,
        message_contains: str | None = None,
        start_index: pydantic.NonNegativeInt | None = None,
        count_limit: pydantic.PositiveInt | None = None,
    ) -> list[dict[str, str]]:
        """Return events for a specified run

        Parameters
        ----------
        run_id : str
            the unique identifier of the run to query
        message_contains : str, optional
            filter to events with message containing this expression, by default None
        start_index : typing.int, optional
            slice results returning only those above this index, by default None
        count_limit : typing.int, optional
            limit number of returned results, by default None

        Returns
        -------
        list[dict[str, str]]
            list of matching events containing entries with message and timestamp data

        Raises
        ------
        RuntimeError
            if there was a failure retrieving information from the server
        """

        msg_filter: str = (
            json.dumps([f"event.message contains {message_contains}"])
            if message_contains
            else ""
        )

        params: dict[str, str | int] = {
            "run": run_id,
            "filters": msg_filter,
            "start": start_index or 0,
            "count": count_limit or 0,
        }

        response = requests.get(
            f"{self._user_config.server.url}/events",
            headers=self._headers,
            params=params,
        )

        json_response = get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of events for run '{run_id}'",
            response=response,
        )

        return json_response.get("data", [])

    @prettify_pydantic
    @pydantic.validate_call
    def get_alerts(
        self,
        *,
        run_id: str | None = None,
        critical_only: bool = True,
        names_only: bool = True,
        start_index: pydantic.NonNegativeInt | None = None,
        count_limit: pydantic.PositiveInt | None = None,
        sort_by_columns: list[tuple[str, bool]] | None = None,
    ) -> list[AlertBase] | list[str | None]:
        """Retrieve alerts for a given run

        Parameters
        ----------
        run_id : str | None
            The ID of the run to find alerts for
        critical_only : bool, optional
            If a run is specified, whether to only return details about alerts which are currently critical, by default True
        names_only: bool, optional
            Whether to only return the names of the alerts (otherwise return the full details of the alerts), by default True
        start_index : typing.int, optional
            slice results returning only those above this index, by default None
        count_limit : typing.int, optional
            limit number of returned results, by default None
        sort_by_columns : list[tuple[str, bool]], optional
            sort by columns in the order given,
            list of tuples in the form (column_name: str, sort_descending: bool),
            default is None.

        Returns
        -------
        list[dict[str, Any]]
            a list of all alerts for this run which match the constrains specified

        Raises
        ------
        RuntimeError
            if there was a failure retrieving data from the server
        """
        if not run_id:
            if critical_only:
                raise RuntimeError(
                    "critical_only is ambiguous when returning alerts with no run ID specified."
                )
            return [
                alert.name if names_only else alert
                for _, alert in Alert.get(
                    sorting=[
                        dict(zip(("column", "descending"), a)) for a in sort_by_columns
                    ]
                    if sort_by_columns
                    else None,
                )
            ]  # type: ignore

        if sort_by_columns:
            logger.warning(
                "Run identifier specified for alert retrieval,"
                " argument 'sort_by_columns' will be ignored"
            )

        _alerts = [
            Alert(identifier=alert.get("id"), **alert)
            for alert in Run(identifier=run_id).get_alert_details()
        ]

        return [
            alert.name if names_only else alert
            for alert in _alerts
            if not critical_only or alert.get_status(run_id) == "critical"
        ]

    @prettify_pydantic
    @pydantic.validate_call
    def get_tags(
        self,
        *,
        start_index: pydantic.NonNegativeInt | None = None,
        count_limit: pydantic.PositiveInt | None = None,
        sort_by_columns: list[tuple[str, bool]] | None = None,
    ) -> typing.Generator[Tag, None, None]:
        """Retrieve tags

        Parameters
        ----------
        start_index : typing.int, optional
            slice results returning only those above this index, by default None
        count_limit : typing.int, optional
            limit number of returned results, by default None
        sort_by_columns : list[tuple[str, bool]], optional
            sort by columns in the order given,
            list of tuples in the form (column_name: str, sort_descending: bool),
            default is None.

        Returns
        -------
        yields
            tag identifier
            tag object

        Raises
        ------
        RuntimeError
            if there was a failure retrieving data from the server
        """
        return Tag.get(
            count=count_limit,
            offset=start_index,
            sorting=[dict(zip(("column", "descending"), a)) for a in sort_by_columns]
            if sort_by_columns
            else None,
        )

    @prettify_pydantic
    @pydantic.validate_call
    def delete_tag(self, tag_id: str) -> None:
        """Delete a tag by its identifier

        Parameters
        ----------
        tag_id : str
            unique identifier for the tag

        Raises
        ------
        RuntimeError
            if the deletion failed due to a server request error
        """
        with contextlib.suppress(ValueError):
            Tag(identifier=tag_id).delete()

    @prettify_pydantic
    @pydantic.validate_call
    def get_tag(self, tag_id: str) -> Tag:
        """Retrieve a single tag

        Parameters
        ----------
        tag_id : str
            the unique identifier for this tag

        Returns
        -------
        Tag
            response containing information on the given tag

        Raises
        ------
        RuntimeError
            if retrieval of information from the server on this tag failed
        ObjectNotFoundError
            if tag does not exist
        """
        return Tag(identifier=tag_id)
