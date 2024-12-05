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

    def __new__(cls, identifier: str | None = None, **kwargs):
        """Retrieve an object representing an storage either locally or on the server by id"""
        _storage_pre = StorageBase(identifier=identifier, **kwargs)
        if _storage_pre.type == "S3":
            return S3Storage(identifier=identifier, **kwargs)
        elif _storage_pre.type == "File":
            return FileStorage(identifier=identifier, **kwargs)

        raise RuntimeError(f"Unknown type '{_storage_pre.type}'")

    @classmethod
    @pydantic.validate_call
    def get(
        cls, count: int | None = None, offset: int | None = None, **kwargs
    ) -> typing.Generator[tuple[str, FileStorage | S3Storage], None, None]:
        # Currently no storage filters
        kwargs.pop("filters", None)

        _class_instance = StorageBase(read_only=True, **kwargs)
        _url = f"{_class_instance._base_url}"
        _response = sv_get(
            _url,
            headers=_class_instance._headers,
            params={"start": offset, "count": count},
        )
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {_class_instance.__class__.__name__.lower()}s",
            expected_type=list,
        )

        _out_dict: dict[str, FileStorage | S3Storage] = {}

        for _entry in _json_response:
            _id = _entry.pop("id")
            if _entry["type"] == "S3":
                yield _entry["id"], S3Storage(read_only=True, identifier=_id, **_entry)
            elif _entry["type"] == "File":
                yield (
                    _entry["id"],
                    FileStorage(read_only=True, identifier=_id, **_entry),
                )
            else:
                raise RuntimeError(f"Unrecognised storage type '{_entry['type']}'")
