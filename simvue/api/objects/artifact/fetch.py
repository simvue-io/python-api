"""Simvue Artifact Retrieval.

To simplify case whereby user does not know the artifact type associated
with an identifier, use a generic artifact object.
"""

import http
import json
import typing
from collections.abc import Generator

import pydantic

from simvue.api.objects.artifact.base import ArtifactBase
from simvue.api.objects.artifact.object import ObjectArtifact
from simvue.api.objects.base import Sort
from simvue.api.request import get as sv_get
from simvue.api.request import get_json_from_response
from simvue.api.url import URL
from simvue.config.user import SimvueConfiguration
from simvue.exception import ObjectNotFoundError

from .file import FileArtifact

__all__ = ["Artifact"]


class ArtifactSort(Sort):
    @pydantic.field_validator("column")
    @classmethod
    def check_column(cls, column: str) -> str:
        if column and (
            column not in {"name", "created"} and not column.startswith("metadata.")
        ):
            _out_msg: str = f"Invalid sort column for artifacts '{column}'"
            raise ValueError(_out_msg)
        return column


class Artifact:
    """Simvue Artifact.

    Generic Simvue artifact retrieval class.

    """

    def __new__(
        cls,
        identifier: str | None = None,
        *,
        server_url: str | None = None,
        server_token: pydantic.SecretStr | None = None,
        **kwargs: typing.Any,
    ) -> FileArtifact | ObjectArtifact:
        """Retrieve an object representing an artifact on the server by id.

        Parameters
        ----------
        identifier : str
            identifier of storage object to retrieve
        server_url: str | None, optional
            alternative server URL, default None
        server_token : str | None, optional
            token for alternative server, default None
        **kwargs : Any
            additional arguments for retrieval

        Returns
        -------
        FileArtifact | ObjectArtifact
            object representing storage

        """
        _artifact_pre = ArtifactBase(
            identifier=identifier,
            server_url=server_url,
            server_token=server_token,
            **kwargs,
        )
        if _artifact_pre.original_path:
            return FileArtifact(
                identifier=identifier,
                server_url=server_url,
                server_token=server_token,
                **kwargs,
            )
        return ObjectArtifact(
            identifier=identifier,
            server_url=server_url,
            server_token=server_token,
            **kwargs,
        )

    @classmethod
    def from_run(
        cls,
        run_id: str,
        *,
        category: typing.Literal["input", "output", "code"] | None = None,
        server_url: str | None = None,
        server_token: pydantic.SecretStr | None = None,
    ) -> Generator[tuple[str, FileArtifact | ObjectArtifact]]:
        """Return artifacts associated with a given run.

        Parameters
        ----------
        run_id : str
            The ID of the run to retrieve artifacts from
        category : Literal['input', 'output', 'code'] | None
            category of artifacts to return, if None, do not filter
                * input - this file is an input file.
                * output - this file is created by the run.
                * code - this file represents an executed script
        server_url: str | None, optional
            alternative server URL, default None
        server_token : str | None, optional
            token for alternative server, default None

        Returns
        -------
        Generator[tuple[str, FileArtifact | ObjectArtifact]]
            The artifacts

        Yields
        ------
        Iterator[Generator[tuple[str, FileArtifact | ObjectArtifact]]]
            identifier for artifact
            the artifact itself as a class instance

        Raises
        ------
        ObjectNotFoundError
            Raised if artifacts could not be found for that run

        """
        _config: SimvueConfiguration = SimvueConfiguration.fetch(
            mode="online",
            server_url=server_url,
            server_token=server_token,
        )
        _url = URL(f"{_config.server.url}") / f"runs/{run_id}/artifacts"
        _response = sv_get(
            url=f"{_url}",
            params={"category": category},
            headers=_config.headers,
            verify=_config.server_verify,
        )
        _json_response = get_json_from_response(
            expected_type=list,
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Retrieval of artifacts for run '{run_id}'",
        )

        _json_response = typing.cast("list[dict[str, object]]", _json_response)

        if _response.status_code == http.HTTPStatus.NOT_FOUND or not _json_response:
            raise ObjectNotFoundError(
                ArtifactBase.label,
                category,
                extra=f"for run '{run_id}'",
            )

        for _entry in _json_response:
            _id = typing.cast("str | None", _entry.pop("id"))
            yield (
                _id,
                Artifact(_local=True, _read_only=True, identifier=_id, **_entry),
            )

    @classmethod
    def from_name(
        cls,
        run_id: str,
        name: str,
        *,
        force_overwrite: bool = False,
        server_url: str | None = None,
        server_token: pydantic.SecretStr | None = None,
    ) -> FileArtifact | ObjectArtifact | None:
        """Retrieve an artifact by name.

        Parameters
        ----------
        run_id : str
            the identifier of the run to retrieve from.
        name : str
            the name of the artifact to retrieve.
        force_overwrite : bool, optional
            if duplicates are detected force download
            the first match, default of False
            will raise an exception
        server_url: str | None, optional
            alternative server URL, default None
        server_token : str | None, optional
            token for alternative server, default None

        Returns
        -------
        FileArtifact | ObjectArtifact | None
            the artifact if found

        Raises
        ------
        RuntimeError
            when duplicate artifacts are found within a single run

        """
        _config: SimvueConfiguration = SimvueConfiguration.fetch(
            mode="online",
            server_url=server_url,
            server_token=server_token,
        )
        _url = URL(f"{_config.server.url}") / f"runs/{run_id}/artifacts"
        _response = sv_get(
            url=f"{_url}",
            params={"name": name},
            headers=_config.headers,
            verify=_config.server_verify,
        )
        if _response.status_code == http.HTTPStatus.NOT_FOUND:
            return None

        _json_response = get_json_from_response(
            expected_type=list,
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of artifact '{name}' for run '{run_id}'",
        )
        _json_response = typing.cast("list[dict[str, object]]", _json_response)

        if _response.status_code == http.HTTPStatus.NOT_FOUND or not _json_response:
            raise ObjectNotFoundError(
                ArtifactBase.label(),
                name,
                extra=f"for run '{run_id}'",
            )

        if (_n_res := len(_json_response)) > 1 and not force_overwrite:
            _out_msg: str = (
                f"Expected single result for artifact '{name}' for run '{run_id}'"
                + f" but got {_n_res}",
            )
            raise RuntimeError(_out_msg)

        _first_result: dict[str, typing.Any] = _json_response[0]
        _artifact_id: str = _first_result.pop("id")

        return Artifact(
            identifier=_artifact_id,
            run=run_id,
            server_url=server_url,
            server_token=server_token,
            **_first_result,
            _local=True,
        )

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        *,
        count: int | None = None,
        offset: int | None = None,
        sorting: list[ArtifactSort] | None = None,
        server_url: str | None = None,
        server_token: pydantic.SecretStr | None = None,
        **kwargs: typing.Any,
    ) -> Generator[tuple[str, FileArtifact | ObjectArtifact]]:
        """Returns artifacts associated with the current user.

        Parameters
        ----------
        count : int, optional
            limit the number of results, default of None returns all.
        offset : int, optional
            start index for returned results, default of None starts at 0.
        sorting : list[dict] | None, optional
            list of sorting definitions in the form {'column': str, 'descending': bool}
        server_url: str | None, optional
            alternative server URL, default None
        server_token : str | None, optional
            token for alternative server, default None
        **kwargs : Any
            additional arguments for retrieval

        Yields
        ------
        tuple[str, FileArtifact | ObjectArtifact]
            identifier for artifact
            the artifact itself as a class instance

        """
        _config: SimvueConfiguration = SimvueConfiguration.fetch(
            mode="online",
            server_url=server_url,
            server_token=server_token,
        )
        _url = URL(f"{_config.server.url}") / ArtifactBase.endpoint()
        _params = {"start": offset, "count": count}

        if sorting:
            _params["sorting"] = json.dumps([sort.to_params() for sort in sorting])

        _response = sv_get(
            _url,
            headers=_config.headers,
            params=_params | kwargs,
            verify=_config.server_verify,
        )
        _label: str = cls.__name__.lower()
        _label = _label.replace("base", "")
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {_label}s",
        )
        _json_response = typing.cast("dict[str, object]", _json_response)
        _data = typing.cast(
            "list[dict[str, object]] | None", _json_response.get("data")
        )

        if _data is None:
            _out_msg: str = f"Expected key 'data' for retrieval of {_label}s"
            raise RuntimeError(_out_msg)

        for _entry in _data:
            _id = typing.cast("str", _entry.pop("id"))
            yield (
                _id,
                Artifact(_local=True, _read_only=True, identifier=_id, **_entry),
            )
