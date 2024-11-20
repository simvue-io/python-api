"""
Simvue Artifact
===============

Class for defining and interacting with artifact objects.

"""

import http
import typing
import pydantic
import os.path
import sys

from simvue.models import NAME_REGEX
from simvue.utilities import get_mimetype_for_file, get_mimetypes, calculate_sha256
from simvue.api.objects.base import SimvueObject
from simvue.serialization import serialize_object
from simvue.api.request import put as sv_put, get_json_from_response

Category = typing.Literal["code", "input", "output"]

UPLOAD_TIMEOUT: int = 30


class Artifact(SimvueObject):
    """Connect to/create an artifact locally or on the server"""

    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        super().__init__(identifier, **kwargs)
        self._storage_url: str | None = None
        self._label = "artifact"

    @classmethod
    def new(cls, *_, **__) -> None:
        raise NotImplementedError(
            "No method 'new' for type 'artifact', use 'new_file' or 'new_object'"
        )

    @classmethod
    @pydantic.validate_call
    def new_file(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        run: str,
        storage: str | None,
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
        run : str
            the identifier with which this artifact is associated
        storage : str | None
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

        _upload_data = {
            "name": name,
            "storage": storage,
            "category": category,
            "originalPath": os.path.expandvars(_file_orig_path),
            "size": _file_size,
            "type": _file_type,
            "checksum": _file_checksum,
        }

        _artifact = Artifact(_read_only=False, **_upload_data)

        _artifact.offline_mode(offline)

        with open(file_path, "rb") as out_f:
            _artifact._upload(artifact_data=out_f, run_id=run, **_upload_data)

        return _artifact

    @classmethod
    @pydantic.validate_call
    def new_object(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        run: str,
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
        run : str
            the identifier with which this artifact is associated
        storage : str | None
            the identifier for the storage location for this object
        category : "code" | "input" | "output"
            the category of this artifact
        obj : Any
            object to serialize and upload
        allow_pickling : bool, optional
            whether to allow the object to be pickled if no other
            serialiazation found. Default is True
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
        _upload_data = {
            "name": name,
            "storage": storage,
            "category": category,
            "originalPath": "",
            "size": sys.getsizeof(obj),
            "type": _data_type,
            "checksum": _checksum,
        }

        _artifact = Artifact(read_only=False, **_upload_data)
        _artifact.offline_mode(offline)
        _artifact._upload(artifact_data=_serialized, run_id=run, **_upload_data)
        return _artifact

    def _post(self, **kwargs) -> dict[str, typing.Any]:
        # The ID is the checksum, set this only if the post
        # to server was successful (else offline_ prefix kept)
        _identifier = self._staging["checksum"]
        _response = super()._post(**kwargs)
        self._storage_url = _response.get("url")
        self._identifier = _identifier
        return _response

    def commit(self) -> None:
        raise TypeError("Cannot call method 'commit' on write-once type 'Artifact'")

    def _upload(
        self, artifact_data: typing.Any, run_id: str, **_obj_parameters
    ) -> None:
        # If local file store then do nothing
        if not self.storage_url or self._offline:
            return

        # NOTE: Assumes URL for Run is always same format as Artifact
        _run_artifacts_url: str = self._base_url.replace(self._label, "run")

        _response = sv_put(
            url=self._storage_url,
            headers={},
            data=artifact_data,
            is_json=False,
            timeout=UPLOAD_TIMEOUT,
        )

        self._logger.debug(
            "Got status code %d when uploading artifact",
            _response.status_code,
        )

        get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"uploading artifact '{self.name}' to object storage",
            response=_response,
        )

        sv_put(
            url=_run_artifacts_url,
            headers=self._headers,
            data=_obj_parameters | {self.storage},
        )

        get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding artifact '{self.name}' to run '{run_id}'",
            response=_response,
        )

    @property
    def name(self) -> str:
        """Retrieve the name for this artifact"""
        return self._get_attribute("name")

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
    def storage(self) -> str:
        """Retrieve the storage identifier for this artifact"""
        return self._get_attribute("storage")

    @property
    def type(self) -> str:
        """Retrieve the MIME type for this artifact"""
        return self._get_attribute("type")

    @property
    def storage_url(self) -> str | None:
        """Retrieve storage URL for the artifact"""
        return self._storage_url
