import http
import typing
import pydantic
import json

from simvue.api.objects.artifact.base import ArtifactBase
from simvue.api.objects.base import Sort
from .file import FileArtifact
from simvue.api.objects.artifact.object import ObjectArtifact
from simvue.api.request import get_json_from_response, get as sv_get
from simvue.api.url import URL
from simvue.exception import ObjectNotFoundError


__all__ = ["Artifact"]


class ArtifactSort(Sort):
    @pydantic.field_validator("column")
    @classmethod
    def check_column(cls, column: str) -> str:
        if column and (
            column not in ("name", "created") and not column.startswith("metadata.")
        ):
            raise ValueError(f"Invalid sort column for artifacts '{column}'")
        return column


class Artifact:
    """Generic Simvue artifact retrieval class"""

    def __init__(self, identifier: str | None = None, *args, **kwargs) -> None:
        """Initialise an instance of generic artifact retriever.

        Parameters
        ----------
        identifier : str
            identifier of artifact object to retrieve
        """
        super().__init__(identifier=identifier, *args, **kwargs)

    def __new__(cls, identifier: str | None = None, **kwargs):
        """Retrieve an object representing an Artifact by id"""
        _artifact_pre = ArtifactBase(identifier=identifier, **kwargs)
        if _artifact_pre.original_path:
            return FileArtifact(identifier=identifier, **kwargs)
        else:
            return ObjectArtifact(identifier=identifier, **kwargs)

    @classmethod
    def from_run(
        cls,
        run_id: str,
        category: typing.Literal["input", "output", "code"] | None = None,
        **kwargs,
    ) -> typing.Generator[tuple[str, FileArtifact | ObjectArtifact], None, None]:
        """Return artifacts associated with a given run.

        Parameters
        ----------
        run_id : str
            The ID of the run to retriece artifacts from
        category : Literal['input', 'output', 'code'] | None
            category of artifacts to return, if None, do not filter
                * input - this file is an input file.
                * output - this file is created by the run.
                * code - this file represents an executed script

        Returns
        -------
        typing.Generator[tuple[str, FileArtifact | ObjectArtifact], None, None]
            The artifacts

        Yields
        ------
        Iterator[typing.Generator[tuple[str, FileArtifact | ObjectArtifact], None, None]]
            identifier for artifact
            the artifact itself as a class instance

        Raises
        ------
        ObjectNotFoundError
            Raised if artifacts could not be found for that run
        """
        _temp = ArtifactBase(**kwargs)
        _url = URL(_temp._user_config.server.url) / f"runs/{run_id}/artifacts"
        _response = sv_get(
            url=f"{_url}", params={"category": category}, headers=_temp._headers
        )
        _json_response = get_json_from_response(
            expected_type=list,
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Retrieval of artifacts for run '{run_id}'",
        )

        if _response.status_code == http.HTTPStatus.NOT_FOUND or not _json_response:
            raise ObjectNotFoundError(
                _temp._label, category, extra=f"for run '{run_id}'"
            )

        for _entry in _json_response:
            _id = _entry.pop("id")
            yield (
                _id,
                Artifact(_local=True, _read_only=True, identifier=_id, **_entry),
            )

    @classmethod
    def from_name(
        cls, run_id: str, name: str, **kwargs
    ) -> typing.Union[FileArtifact | ObjectArtifact, None]:
        """Retrieve an artifact by name.

        Parameters
        ----------
        run_id : str
            the identifier of the run to retrieve from.
        name : str
            the name of the artifact to retrieve.

        Returns
        -------
        FileArtifact | ObjectArtifact | None
            the artifact if found
        """
        _temp = ArtifactBase(**kwargs)
        _url = URL(_temp._user_config.server.url) / f"runs/{run_id}/artifacts"
        _response = sv_get(url=f"{_url}", params={"name": name}, headers=_temp._headers)
        _json_response = get_json_from_response(
            expected_type=list,
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Retrieval of artifact '{name}' for run '{run_id}'",
        )

        if _response.status_code == http.HTTPStatus.NOT_FOUND or not _json_response:
            raise ObjectNotFoundError(_temp._label, name, extra=f"for run '{run_id}'")

        if (_n_res := len(_json_response)) > 1:
            raise RuntimeError(
                f"Expected single result for artifact '{name}' for run '{run_id}'"
                f" but got {_n_res}"
            )

        _first_result: dict[str, typing.Any] = _json_response[0]
        _artifact_id: str = _first_result.pop("id")

        return Artifact(
            identifier=_artifact_id,
            run=run_id,
            **_first_result,
            _read_only=True,
            _local=True,
        )

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        count: int | None = None,
        offset: int | None = None,
        sorting: list[ArtifactSort] | None = None,
        **kwargs,
    ) -> typing.Generator[tuple[str, FileArtifact | ObjectArtifact], None, None]:
        """Returns artifacts associated with the current user.

        Parameters
        ----------
        count : int, optional
            limit the number of results, default of None returns all.
        offset : int, optional
            start index for returned results, default of None starts at 0.
        sorting : list[dict] | None, optional
            list of sorting definitions in the form {'column': str, 'descending': bool}

        Yields
        ------
        tuple[str, FileArtifact | ObjectArtifact]
            identifier for artifact
            the artifact itself as a class instance
        """

        _class_instance = ArtifactBase(_local=True, _read_only=True)
        _url = f"{_class_instance._base_url}"
        _params = {"start": offset, "count": count}

        if sorting:
            _params["sorting"] = json.dumps([sort.to_params() for sort in sorting])

        _response = sv_get(
            _url,
            headers=_class_instance._headers,
            params=_params | kwargs,
        )
        _label: str = _class_instance.__class__.__name__.lower()
        _label = _label.replace("base", "")
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {_label}s",
        )

        if (_data := _json_response.get("data")) is None:
            raise RuntimeError(f"Expected key 'data' for retrieval of {_label}s")

        for _entry in _data:
            _id = _entry.pop("id")
            yield (
                _id,
                Artifact(_local=True, _read_only=True, identifier=_id, **_entry),
            )
