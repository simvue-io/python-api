"""Simvue Artifact.

Class for defining and interacting with artifact objects.

"""

import datetime
import http
import io
import typing
from collections.abc import Generator

import pydantic

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035

from simvue.api.objects.base import SimvueObject, staging_check, write_only
from simvue.api.objects.run import Run
from simvue.api.request import (
    get as sv_get,
)
from simvue.api.request import (
    get_json_from_response,
)
from simvue.api.request import (
    post as sv_post,
)
from simvue.api.request import (
    put as sv_put,
)
from simvue.api.url import URL
from simvue.exception import ObjectNotFoundError
from simvue.models import DATETIME_FORMAT

Category = typing.Literal["code", "input", "output"]

BASE_TIMEOUT: int = 10
UPLOAD_TIMEOUT_PER_MB: int = 1
DOWNLOAD_TIMEOUT_PER_MB: int = 1
DOWNLOAD_CHUNK_SIZE: int = 8192


class ArtifactBase(SimvueObject):
    """Connect to/create an artifact locally or on the server."""

    def __init__(
        self,
        identifier: str | None = None,
        *,
        _read_only: bool = True,
        **kwargs: object,
    ) -> None:
        """Initialise an artifact connection.

        Parameters
        ----------
        identifier : str, optional
            the identifier of this object on the server.
        """
        self._label: str = "artifact"
        self._endpoint: str = f"{self._label}s"
        super().__init__(identifier=identifier, _read_only=_read_only, **kwargs)  # pyright: ignore[reportArgumentType]

        # If the artifact is an online instance, need a place to store the response
        # from the initial creation
        self._init_data: dict[str, dict[str, object]] = {}

    @classmethod
    @override
    def new(cls, *_: object, **__: object) -> Self:
        raise NotImplementedError

    @override
    def commit(self) -> None:
        """Not applicable, cannot commit single write artifact."""
        self._logger.info("Cannot call method 'commit' on write-once type 'Artifact'")

    def attach_to_run(
        self, run_id: str, category: Category
    ) -> dict[str, object] | None:
        """Attach this artifact to a given run.

        Parameters
        ----------
        run_id : str
            identifier of run to associate this artifact with.
        category : Literal['input', 'output', 'code']
            category of this artifact with respect to the run.

        Returns
        -------
        dict[str, object] | None
            response from server or None if offline
        """
        self._init_data["runs"][run_id] = category

        if self._offline:
            self._staging["runs"] = self._init_data["runs"]
            _ = super().commit()
            return None

        _run_artifacts_url = (
            URL(self._user_config.server.url)
            / f"runs/{run_id}/artifacts/{self._init_data['id']}"
        )

        _response = sv_put(
            url=f"{_run_artifacts_url}",
            headers=self._headers,
            json={"category": category},
        )

        _json_response = get_json_from_response(
            expected_status=[http.HTTPStatus.OK],
            scenario=f"adding artifact '{self.name}' to run '{run_id}'",
            response=_response,
        )

        return typing.cast("dict[str, object]", _json_response)

    @override
    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        """Perform operation when this artifact is switched from offline to online mode.

        Parameters
        ----------
        id_mapping : dict[str, str]
            mapping from offline identifier to new online identifier.
        """
        _offline_staging = typing.cast(
            "dict[str, Category]", self._init_data["runs"].copy()
        )
        for _id, category in _offline_staging.items():
            _ = self.attach_to_run(run_id=id_mapping[_id], category=category)

    def _upload(
        self, file: io.BytesIO | io.BufferedReader, timeout: int | None, file_size: int
    ) -> None:
        if self._offline:
            _ = super().commit()
            return

        if not (_url := self._staging.get("url")):
            return

        if not timeout:
            timeout = BASE_TIMEOUT + UPLOAD_TIMEOUT_PER_MB * file_size // 1024 // 1024

        self._logger.debug(
            "Will wait for a period of %.0fs for upload of file "
            "for %dB file to complete.",
            timeout,
            file_size,
        )

        _name = self._staging["name"]

        _response = sv_post(
            url=_url,
            headers={},
            params={},
            is_json=False,
            timeout=timeout,
            files={"file": file},
            data=self._init_data.get("fields"),
        )

        self._logger.debug(
            "Got status code %d when uploading artifact",
            _response.status_code,
        )

        _ = get_json_from_response(
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NO_CONTENT],
            allow_parse_failure=True,  # JSON response from S3 not parsible
            scenario=f"uploading artifact '{_name}' to object storage",
            response=_response,
        )

        # Temporarily remove read-only state
        self.read_only(is_read_only=False)

        # Update the server status to confirm file uploaded
        self.uploaded = True
        _ = super().commit()
        self.read_only(is_read_only=True)

    @override
    def _get(
        self, url: str | None = None, storage: str | None = None, **kwargs: object
    ) -> dict[str, typing.Any]:
        return super()._get(
            storage=storage or self._staging.get("server", {}).get("storage_id"),
            url=url,
            **kwargs,  # pyright: ignore[reportArgumentType]
        )

    @property
    def checksum(self) -> str:
        """Retrieve the checksum for this artifact.

        Returns
        -------
        str
        """
        return typing.cast("str", self._get_attribute("checksum"))

    @property
    def storage_url(self) -> URL | None:
        """Retrieve upload URL for artifact.

        Returns
        -------
        simvue.api.url.URL | None
        """
        _url = typing.cast("str | None", self._init_data.get("url"))
        return URL(_url) if _url else None

    @property
    def original_path(self) -> str:
        """Retrieve the original path of the file associated with this artifact.

        Returns
        -------
        str
        """
        return typing.cast("str", self._get_attribute("original_path"))

    @property
    def storage_id(self) -> str | None:
        """Retrieve the storage identifier for this artifact.

        Returns
        -------
        str | None
        """
        return typing.cast("str | None", self._get_attribute("storage_id"))

    @property
    def mime_type(self) -> str:
        """Retrieve the MIME type for this artifact.

        Returns
        -------
        str
        """
        return typing.cast("str", self._get_attribute("mime_type"))

    @property
    def size(self) -> int:
        """Retrieve the size for this artifact in bytes.

        Returns
        -------
        int
        """
        return typing.cast("int", self._get_attribute("size"))

    @property
    def name(self) -> str | None:
        """Retrieve name for the artifact.

        Returns
        -------
        str | None
        """
        return typing.cast("str | None", self._get_attribute("name"))

    @property
    def created(self) -> datetime.datetime | None:
        """Retrieve created datetime for the artifact.

        Returns
        -------
        datetime.datetime | None
        """
        _created: str | None = typing.cast("str | None", self._get_attribute("created"))
        return (
            datetime.datetime.strptime(_created, DATETIME_FORMAT).replace(
                tzinfo=datetime.UTC
            )
            if _created
            else None
        )

    @property
    @staging_check
    def uploaded(self) -> bool:
        """Returns whether a file was uploaded for this artifact.

        Returns
        -------
        bool
        """
        return typing.cast("bool", self._get_attribute("uploaded"))

    @uploaded.setter
    @write_only
    @pydantic.validate_call
    def uploaded(self, is_uploaded: bool) -> None:
        """Set if a file was successfully uploaded for this artifact."""
        self._staging["uploaded"] = is_uploaded

    @property
    def download_url(self) -> URL | None:
        """Retrieve the URL for downloading this artifact.

        Returns
        -------
        simvue.api.url.URL | None
        """
        return typing.cast("URL", self._get_attribute("url"))

    @property
    def runs(self) -> Generator[str]:
        """Retrieve all runs for which this artifact is related.

        Yields
        ------
        str
            run identifier for run associated with this artifact

        Returns
        -------
        Generator[str, None, None]
        """
        for _id, _ in Run.get(filters=[f"artifact.id == {self.id}"]):
            yield _id

    def get_category(self, run_id: str) -> Category:
        """Retrieve the category of this artifact with respect to a given run.

        Returns
        -------
        Literal['input', 'output', 'code']
        """
        _run_url = (
            URL(self._user_config.server.url)
            / f"runs/{run_id}/artifacts/{self._identifier}"
        )
        _response = sv_get(url=f"{_run_url}", headers=self._headers)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND],
            scenario=(
                f"Retrieval of category for artifact '{self._identifier}' "
                f"with respect to run '{run_id}'"
            ),
        )
        _json_response = typing.cast("dict[str, object]", _json_response)
        if _response.status_code == http.HTTPStatus.NOT_FOUND:
            raise ObjectNotFoundError(
                self._label, self._identifier or "unknown", extra=f"for run '{run_id}'"
            )

        return typing.cast("Category", _json_response["category"])

    @pydantic.validate_call
    def download_content(self) -> Generator[bytes]:
        """Stream artifact content.

        Yields
        ------
        bytes
            artifact content from server.

        Returns
        -------
        Generator[bytes, None, None]
        """
        if not self.download_url:
            _out_msg: str = f"Could not retrieve URL for artifact '{self._identifier}'"
            raise ValueError(_out_msg)

        _timeout: int = (
            BASE_TIMEOUT + DOWNLOAD_TIMEOUT_PER_MB * self.size // 1024 // 1024
        )

        self._logger.debug(
            "Will wait %.0fs for download of file %s of size %dB",
            _timeout,
            self.name,
            self.size,
        )

        _response = sv_get(
            f"{self.download_url}",
            timeout=_timeout,
            headers=None,
        )

        _ = get_json_from_response(
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
