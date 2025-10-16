"""
Simvue Storage Retrieval
==============--========

To simplify case whereby user does not know the storage type associated
with an identifier, use a generic storage object.
"""

import typing
import http
import pydantic

from simvue.api.request import get_json_from_response
from simvue.api.request import get as sv_get

from .s3 import S3Storage
from .file import FileStorage
from .base import StorageBase


class Storage:
    """Generic Simvue storage retrieval class"""

    def __init__(self, identifier: str | None = None, *args, **kwargs) -> None:
        """Initialise an instance of generic storage retriever.

        Parameters
        ----------
        identifier : str
            identifier of storage object to retrieve
        """
        super().__init__(identifier=identifier, *args, **kwargs)

    def __new__(cls, identifier: str | None = None, **kwargs):
        """Retrieve an object representing an storage either locally or on the server by id"""
        _storage_pre = StorageBase(identifier=identifier, **kwargs)
        if _storage_pre.backend == "S3":
            return S3Storage(identifier=identifier, **kwargs)
        elif _storage_pre.backend == "File":
            return FileStorage(identifier=identifier, **kwargs)

        raise RuntimeError(f"Unknown backend '{_storage_pre.backend}'")

    @classmethod
    @pydantic.validate_call
    def get(
        cls, count: int | None = None, offset: int | None = None, **kwargs
    ) -> typing.Generator[tuple[str, FileStorage | S3Storage], None, None]:
        """Returns storage systems accessible to the current user.

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
        kwargs.pop("filters", None)

        _class_instance = StorageBase(_local=True, _read_only=True)
        _url = f"{_class_instance._base_url}"
        _response = sv_get(
            _url,
            headers=_class_instance._headers,
            params={"start": offset, "count": count} | kwargs,
        )
        _label: str = _class_instance.__class__.__name__.lower()
        _label = _label.replace("base", "")
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {_label}s",
            expected_type=list,
        )

        _out_dict: dict[str, FileStorage | S3Storage] = {}

        for _entry in _json_response:
            _id = _entry.pop("id")
            if _entry["backend"] == "S3":
                yield (
                    _id,
                    S3Storage(_local=True, _read_only=True, identifier=_id, **_entry),
                )
            elif _entry["backend"] == "File":
                yield (
                    _id,
                    FileStorage(_local=True, _read_only=True, identifier=_id, **_entry),
                )
            else:
                raise RuntimeError(
                    f"Unrecognised storage backend '{_entry['backend']}'"
                )
