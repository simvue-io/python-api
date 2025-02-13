"""
Simvue Artifact
===============

Class for defining and interacting with artifact objects.

"""

import datetime
import http
import io
import typing
import pydantic

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: F401

from simvue.api.url import URL
from simvue.exception import ObjectNotFoundError
from simvue.models import DATETIME_FORMAT
from simvue.api.objects.base import SimvueObject, staging_check, write_only
from simvue.api.objects.run import Run
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


class ArtifactBase(SimvueObject):
    """Connect to/create an artifact locally or on the server"""

    def __init__(
        self, identifier: str | None = None, _read_only: bool = True, **kwargs
    ) -> None:
        self._label = "artifact"
        self._endpoint = f"{self._label}s"
        super().__init__(identifier=identifier, _read_only=_read_only, **kwargs)

        # If the artifact is an online instance, need a place to store the response
        # from the initial creation
        self._init_data: dict[str, dict] = {}

    def commit(self) -> None:
        self._logger.info("Cannot call method 'commit' on write-once type 'Artifact'")

    def attach_to_run(self, run_id: str, category: Category) -> None:
        """Attach this artifact to a given run"""
        self._init_data["runs"][run_id] = category

        if self._offline:
            self._staging["runs"] = self._init_data["runs"]
            super().commit()
            return

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
            scenario=f"adding artifact '{self.name}' to run '{run_id}'",
            response=_response,
        )

    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        _offline_staging = self._init_data["runs"].copy()
        for id, category in _offline_staging.items():
            self.attach_to_run(run_id=id_mapping[id], category=category)

    def _upload(self, file: io.BytesIO) -> None:
        if self._offline:
            super().commit()
            return

        if not (_url := self._staging.get("url")):
            return

        _name = self._staging["name"]

        _response = sv_post(
            url=_url,
            headers={},
            params={},
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

        # Temporarily remove read-only state
        self.read_only(False)

        # Update the server status to confirm file uploaded
        self.uploaded = True
        super().commit()
        self.read_only(True)

    def _get(
        self, storage: str | None = None, url: str | None = None, **kwargs
    ) -> dict[str, typing.Any]:
        return super()._get(
            storage=storage or self._staging.get("server", {}).get("storage_id"),
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
        return self._get_attribute("original_path")

    @property
    def storage_id(self) -> str | None:
        """Retrieve the storage identifier for this artifact"""
        return self._get_attribute("storage_id")

    @property
    def mime_type(self) -> str:
        """Retrieve the MIME type for this artifact"""
        return self._get_attribute("mime_type")

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

    @property
    @staging_check
    def uploaded(self) -> bool:
        """Returns whether a file was uploaded for this artifact."""
        return self._get_attribute("uploaded")

    @uploaded.setter
    @write_only
    @pydantic.validate_call
    def uploaded(self, is_uploaded: bool) -> None:
        """Set if a file was successfully uploaded for this artifact."""
        self._staging["uploaded"] = is_uploaded

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
            f"{self.download_url}", timeout=DOWNLOAD_TIMEOUT, headers=None
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
