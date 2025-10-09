"""Simvue Storage Retrieval.

To simplify case whereby user does not know the storage type associated
with an identifier, use a generic storage object.
"""

import http
import typing
from collections.abc import Generator

import pydantic

from simvue.api.request import get as sv_get
from simvue.api.request import get_json_from_response
from simvue.config.user import SimvueConfiguration

from .base import StorageBase
from .file import FileStorage
from .s3 import S3Storage


class Storage:
    """Generic Simvue storage retrieval class."""

    def __init__(
        self,
        identifier: str | None = None,
        *,
        _read_only: bool = False,
        _offline: bool = False,
        _user_agent: str | None = None,
        _local: bool = False,
        **kwargs: object,
    ) -> None:
        """Initialise an instance of generic storage retriever.

        Parameters
        ----------
        identifier : str
            identifier of storage object to retrieve
        """

    def __new__(
        cls,
        identifier: str | None = None,
        *,
        _read_only: bool = False,
        _offline: bool = False,
        _user_agent: str | None = None,
        _local: bool = False,
        **kwargs: object,
    ) -> S3Storage | FileStorage:
        """Retrieve a storage object either locally or on the server by id."""
        _storage_pre = StorageBase(
            identifier=identifier,
            _read_only=True,
            _local=True,
            _offline=False,
            _user_agent=None,
        )
        if _storage_pre.backend == "S3":
            return S3Storage(
                _local=True,
                _read_only=True,
                identifier=identifier,
                _user_agent=None,
                _offline=False,
                **kwargs,
            )
        if _storage_pre.backend == "File":
            return FileStorage(
                _local=True,
                _read_only=True,
                identifier=identifier,
                _user_agent=None,
                _offline=False,
                **kwargs,
            )

        _out_msg: str = f"Unknown backend '{_storage_pre.backend}'"
        raise RuntimeError(_out_msg)

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        count: int | None = None,
        offset: int | None = None,
        **kwargs: str | float | None,
    ) -> Generator[tuple[str, FileStorage | S3Storage]]:
        """Return storage systems accessible to the current user.

        Parameters
        ----------
        count : int, optional
            limit the number of results, default of None returns all.
        offset : int, optional
            start index for returned results, default of None starts at 0.

        Yields
        ------
        tuple[str, FileStorage | S3Storage]
            identifier for a storage
            the storage itself as a class instance
        """
        # Currently no storage filters
        _ = kwargs.pop("filters", None)

        _class_instance = StorageBase(_local=True, _read_only=True)
        _config: SimvueConfiguration = SimvueConfiguration.fetch()
        _url = f"{_class_instance.base_url}"
        _params: dict[str, int | float | str | None | list[str]] = {
            "start": offset,
            "count": count,
        }
        _params |= kwargs
        _response = sv_get(
            _url,
            headers=_config.headers,  # pyright: ignore[reportUnknownArgumentType]
            params=_params,
        )
        _label: str = _class_instance.__class__.__name__.lower()
        _label = _label.replace("base", "")
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {_label}s",
            expected_type=list,
        )

        _json_response = typing.cast("list[dict[str, object]]", _json_response)

        _out_dict: dict[str, FileStorage | S3Storage] = {}

        for _entry in _json_response:
            _id = typing.cast("str", _entry.pop("id"))
            if _entry["backend"] == "S3":
                yield (
                    _id,
                    S3Storage(
                        _local=True,
                        _read_only=True,
                        identifier=_id,
                        _user_agent=None,
                        _offline=False,
                        **_entry,
                    ),
                )
            elif _entry["backend"] == "File":
                yield (
                    _id,
                    FileStorage(
                        _local=True,
                        _read_only=True,
                        identifier=_id,
                        _user_agent=None,
                        _offline=False,
                        **_entry,
                    ),
                )
            else:
                _out_msg: str = f"Unrecognised storage backend '{_entry['backend']}'"
                raise RuntimeError(_out_msg)
