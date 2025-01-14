"""
Simvue Artifact
===============

Class for defining and interacting with artifact objects.

"""

import datetime
import http
import io
import pathlib
import typing
import pydantic
import os.path
import sys

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from simvue.api.url import URL
from simvue.exception import ObjectNotFoundError
from simvue.models import NAME_REGEX, DATETIME_FORMAT
from simvue.utilities import get_mimetype_for_file, get_mimetypes, calculate_sha256
from simvue.api.objects.base import SimvueObject
from simvue.api.objects.run import Run
from simvue.serialization import serialize_object
from simvue.api.request import (
    put as sv_put,
    get_json_from_response,
    post as sv_post,
    get as sv_get,
)

Category = typing.Literal["code", "input", "output"]

UPLOAD_TIMEOUT: int = 30
DOWNLOAD_TIMEOUT: int = 30
DOWNLOAD_CHUNK_SIZE: int = 8192


class Artifact(SimvueObject):
    """Connect to/create an artifact locally or on the server"""

    def __init__(
        self, identifier: str | None = None, _read_only: bool = True, **kwargs
    ) -> None:
        super().__init__(identifier=identifier, _read_only=_read_only, **kwargs)

        # If the artifact is an online instance, need a place to store the response
        # from the initial creation
        self._init_data: dict[str, dict] = {}
        self._staging |= {"runs": []}

    @classmethod
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        storage_id: str | None,
        checksum: str,
        size: int,
        file_type: str,
        original_path: pathlib.Path | None,
        metadata: dict[str, typing.Any] | None,
        offline: bool = False,
        **kwargs,
    ) -> Self:
        _artifact = Artifact(
            name=name,
            checksum=checksum,
            size=size,
            originalPath=f"{original_path or ''}",
            storage=storage_id,
            type=file_type,
            metadata=metadata,
            _read_only=False,
        )
        _artifact.offline_mode(offline)

        if offline:
            return _artifact

        # Firstly submit a request for a new artifact, remove the run IDs
        # as these are not an argument for artifact creation
        _post_args = _artifact._staging.copy()
        _post_args.pop("runs", None)
        _artifact._init_data = _artifact._post(**_post_args)

        return _artifact

    @classmethod
    @pydantic.validate_call
    def new_file(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        storage_id: str | None,
        file_path: pydantic.FilePath,
        file_type: str | None,
        metadata: dict[str, typing.Any] | None,
        offline: bool = False,
    ) -> Self:
        """Create a new artifact either locally or on the server

        Note all arguments are keyword arguments

        Parameters
        ----------
        name : str
            the name for this artifact
        storage_id : str | None
            the identifier for the storage location for this object
        category : "code" | "input" | "output"
            the category of this artifact
        file_path : pathlib.Path | str
            path to the file this artifact represents
        file_type : str | None
            the mime type for this file, else this is determined
        metadata : dict[str, Any] | None
            supply metadata information for this artifact
        offline : bool, optional
            whether to define this artifact locally, default is False

        """
        _file_type = file_type or get_mimetype_for_file(file_path)

        if _file_type not in get_mimetypes():
            raise ValueError(f"Invalid MIME type '{file_type}' specified")

        _file_size = file_path.stat().st_size
        _file_orig_path = file_path.expanduser().absolute()
        _file_checksum = calculate_sha256(f"{file_path}", is_file=True)

        _artifact = Artifact.new(
            name=name,
            storage_id=storage_id,
            original_path=os.path.expandvars(_file_orig_path),
            size=_file_size,
            file_type=_file_type,
            checksum=_file_checksum,
            offline=offline,
            metadata=metadata,
        )

        with open(file_path, "rb") as out_f:
            _artifact._upload(file=out_f)

        return _artifact

    @classmethod
    @pydantic.validate_call
    def new_object(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        storage: str | None,
        category: Category,
        obj: typing.Any,
        metadata: dict[str, typing.Any] | None,
        allow_pickling: bool = True,
        offline: bool = False,
    ) -> Self:
        """Create a new artifact either locally or on the server

        Note all arguments are keyword arguments

        Parameters
        ----------
        name : str
            the name for this artifact
        storage : str | None
            the identifier for the storage location for this object
        category : "code" | "input" | "output"
            the category of this artifact
        obj : Any
            object to serialize and upload
        metadata : dict[str, Any] | None
            supply metadata information for this artifact
        allow_pickling : bool, optional
            whether to allow the object to be pickled if no other
            serialization found. Default is True
        offline : bool, optional
            whether to define this artifact locally, default is False

        """
        _serialization = serialize_object(obj, allow_pickling)

        if not _serialization or not (_serialized := _serialization[0]):
            raise ValueError(f"Could not serialize object of type '{type(obj)}'")

        if not (_data_type := _serialization[1]) and not allow_pickling:
            raise ValueError(
                f"Could not serialize object of type '{type(obj)}' without pickling"
            )

        _checksum = calculate_sha256(_serialized, is_file=False)

        _artifact = Artifact.new(
            name=name,
            storage=storage,
            size=sys.getsizeof(obj),
            file_type=_data_type,
            checksum=_checksum,
            metadata=metadata,
        )

        _artifact._upload(file=io.BytesIO(_serialized))
        return _artifact

    def commit(self) -> None:
        raise TypeError("Cannot call method 'commit' on write-once type 'Artifact'")

    def attach_to_run(self, run_id: str, category: Category) -> None:
        """Attach this artifact to a given run"""
        self._staging["runs"].append({"id": run_id, "category": category})

        if self._offline:
            super().commit()
            return

        _name = self._staging["name"]
        _run_artifacts_url = (
            URL(self._user_config.server.url)
            / f"runs/{run_id}/artifacts/{self._init_data['id']}"
        )

        _response = sv_put(
            url=f"{_run_artifacts_url}",
            headers=self._headers,
            json={"category": category},
        )

        get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding artifact '{_name}' to run '{run_id}'",
            response=_response,
        )

    def _upload(self, file: io.BytesIO) -> None:
        if self._offline:
            super().commit()
            return

        if _url := self._init_data.get("url"):
            _name = self._staging["name"]

            _response = sv_post(
                url=_url,
                headers={},
                is_json=False,
                files={"file": file},
                data=self._init_data.get("fields"),
            )

            self._logger.debug(
                "Got status code %d when uploading artifact",
                _response.status_code,
            )

            get_json_from_response(
                expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NO_CONTENT],
                allow_parse_failure=True,  # JSON response from S3 not parsible
                scenario=f"uploading artifact '{_name}' to object storage",
                response=_response,
            )

    def _get(
        self, storage: str | None = None, url: str | None = None, **kwargs
    ) -> dict[str, typing.Any]:
        return super()._get(
            storage=storage or self._staging.get("server", {}).get("storage"),
            url=url,
            **kwargs,
        )

    @property
    def checksum(self) -> str:
        """Retrieve the checksum for this artifact"""
        return self._get_attribute("checksum")

    @property
    def storage_url(self) -> URL | None:
        """Retrieve upload URL for artifact"""
        return URL(_url) if (_url := self._init_data.get("url")) else None

    @property
    def original_path(self) -> str:
        """Retrieve the original path of the file associated with this artifact"""
        return self._get_attribute("originalPath")

    @property
    def storage(self) -> str | None:
        """Retrieve the storage identifier for this artifact"""
        return self._get_attribute("storage")

    @property
    def type(self) -> str:
        """Retrieve the MIME type for this artifact"""
        return self._get_attribute("type")

    @property
    def size(self) -> int:
        """Retrieve the size for this artifact in bytes"""
        return self._get_attribute("size")

    @property
    def name(self) -> str | None:
        """Retrieve name for the artifact"""
        return self._get_attribute("name")

    @property
    def created(self) -> datetime.datetime | None:
        """Retrieve created datetime for the artifact"""
        _created: str | None = self._get_attribute("created")
        return (
            datetime.datetime.strptime(_created, DATETIME_FORMAT) if _created else None
        )

    @classmethod
    def from_name(
        cls, run_id: str, name: str, **kwargs
    ) -> typing.Union["Artifact", None]:
        _temp = Artifact(**kwargs)
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

    @property
    def download_url(self) -> URL | None:
        """Retrieve the URL for downloading this artifact"""
        return self._get_attribute("url")

    @property
    def runs(self) -> typing.Generator[str, None, None]:
        """Retrieve all runs for which this artifact is related"""
        for _id, _ in Run.get(filters=[f"artifact.id == {self.id}"]):
            yield _id

    def get_category(self, run_id: str) -> Category:
        """Retrieve the category of this artifact with respect to a given run"""
        _run_url = (
            URL(self._user_config.server.url)
            / f"runs/{run_id}/artifacts/{self._identifier}"
        )
        _response = sv_get(url=_run_url, header=self._headers)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Retrieval of category for artifact '{self._identifier}' with respect to run '{run_id}'",
        )
        if _response.status_code == http.HTTPStatus.NOT_FOUND:
            raise ObjectNotFoundError(
                self._label, self._identifier, extra=f"for run '{run_id}'"
            )

        return _json_response["category"]

    @pydantic.validate_call
    def download_content(self) -> typing.Generator[bytes, None, None]:
        """Stream artifact content"""
        if not self.download_url:
            raise ValueError(
                f"Could not retrieve URL for artifact '{self._identifier}'"
            )
        _response = sv_get(
            f"{self.download_url}",
            headers=self._headers,
            timeout=DOWNLOAD_TIMEOUT,
            params={"storage": self.storage},
        )

        get_json_from_response(
            response=_response,
            allow_parse_failure=True,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of file for {self._label} '{self._identifier}'",
        )

        _total_length: str | None = _response.headers.get("content-length")

        if _total_length is None:
            yield _response.content
        else:
            yield from _response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE)
