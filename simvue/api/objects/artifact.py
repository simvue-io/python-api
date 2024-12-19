"""
Simvue Artifact
===============

Class for defining and interacting with artifact objects.

"""

import http
import pathlib
import typing
import pydantic
import os.path
import functools
import io
import sys
import requests

from simvue.api.url import URL
from simvue.exception import ObjectNotFoundError
from simvue.models import NAME_REGEX
from simvue.utilities import get_mimetype_for_file, get_mimetypes, calculate_sha256
from simvue.api.objects.base import SimvueObject
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
        self,
        identifier: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(identifier, **kwargs)
        self._staging = {"server": kwargs, "storage": {}}
        self._label = "artifact"

    @classmethod
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        run_id: str,
        storage_id: str | None,
        category: Category,
        offline: bool = False,
        **kwargs,
    ) -> typing.Self:
        _artifact = Artifact(
            run=run_id,
            name=name,
            storage=storage_id,
            category=category,
            _read_only=False,
            **kwargs,
        )
        _artifact.offline_mode(offline)

        if offline:
            return _artifact

        # Firstly submit a request for a new artifact
        _response = _artifact._post(**_artifact._staging["server"])

        # If this artifact does not exist a URL will be returned
        _artifact._staging["server"]["url"] = _response.get("url")

        # If a storage ID has been provided store that else retrieve it
        _artifact._staging["server"]["storage"] = storage_id or _response.get(
            "storage_id"
        )
        _artifact._staging["storage"]["data"] = _response.get("fields")
        _artifact._staging["storage"]["files"] = None

        return _artifact

    @classmethod
    @pydantic.validate_call
    def new_file(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        run_id: str,
        storage_id: str | None,
        category: Category,
        file_path: pydantic.FilePath,
        file_type: str | None,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new artifact either locally or on the server

        Note all arguments are keyword arguments

        Parameters
        ----------
        name : str
            the name for this artifact
        run_id : str
            the identifier with which this artifact is associated
        storage_id : str | None
            the identifier for the storage location for this object
        category : "code" | "input" | "output"
            the category of this artifact
        file_path : pathlib.Path | str
            path to the file this artifact represents
        file_type : str | None
            the mime type for this file, else this is determined
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
            run_id=run_id,
            storage_id=storage_id,
            category=category,
            originalPath=os.path.expandvars(_file_orig_path),
            size=_file_size,
            type=_file_type,
            checksum=_file_checksum,
            offline=offline,
        )

        _artifact.offline_mode(offline)

        with open(file_path, "rb") as out_f:
            _artifact._staging["storage"]["files"] = {"file": out_f}
            _artifact._upload()

        return _artifact

    @classmethod
    @pydantic.validate_call
    def new_object(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        run_id: str,
        storage: str | None,
        category: Category,
        obj: typing.Any,
        allow_pickling: bool = True,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new artifact either locally or on the server

        Note all arguments are keyword arguments

        Parameters
        ----------
        name : str
            the name for this artifact
        run_id : str
            the identifier with which this artifact is associated
        storage : str | None
            the identifier for the storage location for this object
        category : "code" | "input" | "output"
            the category of this artifact
        obj : Any
            object to serialize and upload
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
            run_id=run_id,
            name=name,
            storage=storage,
            category=category,
            originalPath="",
            size=sys.getsizeof(obj),
            type=_data_type,
            checksum=_checksum,
        )
        _artifact.offline_mode(offline)

        _artifact._staging["storage"]["files"] = {"file": io.BytesIO(_serialized)}
        _artifact._upload()
        return _artifact

    def commit(self) -> None:
        raise TypeError("Cannot call method 'commit' on write-once type 'Artifact'")

    def _upload(self) -> None:
        if self._offline:
            super().commit()
            return

        _run_id = self._staging["server"]["run"]
        _files = self._staging["storage"]["files"]
        _name = self._staging["server"]["name"]
        _data = self._staging["storage"].get("data")

        _run_artifacts_url: URL = (
            URL(self._user_config.server.url)
            / f"runs/{_run_id}/artifacts/{self._identifier}"
        )

        if _url := self._staging["server"]["url"]:
            _response = sv_post(
                url=_url, headers={}, is_json=False, files=_files, data=_data
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

        if not self._staging["server"].get("storage"):
            return

        _response = sv_put(
            url=f"{_run_artifacts_url}",
            headers=self._headers,
            data=self._staging["server"],
        )

        get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding artifact '{_name}' to run '{_run_id}'",
            response=_response,
        )

    def _get(self, storage: str | None = None, **kwargs) -> dict[str, typing.Any]:
        return super()._get(
            storage=storage or self._staging.get("server", {}).get("storage"), **kwargs
        )

    @property
    def checksum(self) -> str:
        """Retrieve the checksum for this artifact"""
        return self._get_attribute("checksum")

    @property
    def category(self) -> Category:
        """Retrieve the category for this artifact"""
        return self._get_attribute("category")

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
    def name(self) -> str | None:
        """Retrieve name for the artifact"""
        return self._get_attribute("name")

    @classmethod
    def from_name(
        cls, run_id: str, name: str, **kwargs
    ) -> typing.Union["Artifact", None]:
        _temp = Artifact(**kwargs)
        _url = _temp._base_url / f"runs/{run_id}/artifacts"
        _response = sv_get(url=f"{_url}", params={"name": name}, headers=_temp._headers)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Retrieval of artifact '{name}' for run '{run_id}'",
        )

        if _response.status_code == http.HTTPStatus.NOT_FOUND:
            raise ObjectNotFoundError(_temp._label, name, extra=f"for run '{run_id}'")

        return Artifact(run_id=run_id, **_json_response)

    @functools.lru_cache
    def get_storage_url(self, run_id: str | None) -> typing.Any:
        """Retrieve the storage location for a particular run"""
        if not self._identifier:
            raise ValueError("Cannot retrieve artifact, no ID specified")

        _run_id = run_id or self._run_id

        if not _run_id:
            raise ValueError(
                "A run identifier must be specified when downloading an artifact"
            )

        _url = self._base_url / "runs" / run_id / "artifacts" / self._identifier

        _response = sv_get(
            f"{_url}",
            headers=self._headers,
        )

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=f"Retrieval of content for {self._label} '{self._identifier}'",
        )

        if _response.status_code == http.HTTPStatus.NOT_FOUND:
            raise ObjectNotFoundError(
                self._label, self.name, extra=f"for run '{run_id}'"
            )

        if not (_url := _json_response.get("url")):
            raise RuntimeError(
                f"Expected key 'url' for retrieval of artifact '{self.name}'"
            )

        return _url

    @pydantic.validate_call
    def download(
        self, output_file: pathlib.Path, run_id: str | None = None
    ) -> pathlib.Path | None:
        _storage_url = self.get_storage_url(run_id)

        _response = requests.get(
            f"{_storage_url}", stream=True, timeout=DOWNLOAD_TIMEOUT
        )

        get_json_from_response(
            response=_response,
            allow_parse_failure=True,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of file for {self._label} '{self._identifier}'",
        )

        _total_length: str | None = _response.headers.get("content-length")

        if not output_file.parent.is_dir():
            raise ValueError(
                f"Cannot write to '{output_file.parent}', not a directory."
            )

        with output_file.open("wb") as out_f:
            if _total_length is None:
                out_f.write(_response.content)
            else:
                for data in _response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    out_f.write(data)

        return output_file if output_file.exists() else None

    def download_content(self, run_id: str | None = None) -> typing.Any:
        """Download content of artifact from storage"""
        _storage_url = self.get_storage_url(run_id)
        _response = requests.get(_storage_url, timeout=DOWNLOAD_TIMEOUT)

        get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of content for {self._label} '{self._identifier}'",
        )

        return _response.content
