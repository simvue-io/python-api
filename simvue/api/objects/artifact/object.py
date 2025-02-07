from .base import ArtifactBase
from simvue.models import NAME_REGEX
from simvue.serialization import serialize_object
from simvue.utilities import calculate_sha256

import pydantic
import typing
import sys
import io

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class ObjectArtifact(ArtifactBase):
    def __init__(
        self, identifier: str | None = None, _read_only: bool = True, **kwargs
    ) -> None:
        super().__init__(identifier, _read_only, original_path=None, **kwargs)

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        storage: str | None,
        obj: typing.Any,
        metadata: dict[str, typing.Any] | None,
        allow_pickling: bool = True,
        offline: bool = False,
        **kwargs,
    ) -> Self:
        """Create a new artifact either locally or on the server

        Note all arguments are keyword arguments

        Parameters
        ----------
        name : str
            the name for this artifact
        storage : str | None
            the identifier for the storage location for this object
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

        kwargs.pop("size", None)
        kwargs.pop("checksum", None)

        _artifact = ObjectArtifact(
            name=name,
            storage=storage,
            size=sys.getsizeof(_serialized),
            mime_type=_data_type,
            checksum=_checksum,
            metadata=metadata,
            _offline=offline,
            _read_only=False,
            **kwargs,
        )

        if offline:
            _artifact._init_data = {}

        else:
            _artifact._init_data = _artifact._post(**_artifact._staging)
            _artifact._staging["url"] = _artifact._init_data["url"]

        _artifact._init_data["runs"] = kwargs.get("runs") or {}

        if offline:
            return _artifact

        _artifact._upload(file=io.BytesIO(_serialized))
        return _artifact
