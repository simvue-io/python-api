"""Object artifact handling."""

import io
import sys
import typing

import pydantic

from simvue.models import NAME_REGEX
from simvue.serialization import serialize_object
from simvue.utilities import calculate_sha256

from .base import ArtifactBase

if typing.TYPE_CHECKING:
    import pathlib

    from _typeshed import ReadableBuffer

try:
    from typing import Self
except ImportError:
    from typing import Self

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035


class ObjectArtifact(ArtifactBase):
    """Object based artifact modification and creation class."""

    def __init__(
        self,
        identifier: str | None = None,
        *,
        _read_only: bool = True,
        **kwargs: object,
    ) -> None:
        """Initialise a new object artifact connection.

        Parameters
        ----------
        identifier : str, optional
            the identifier of this object on the server.
        """
        _ = kwargs.pop("original_path", None)
        super().__init__(identifier, _read_only=_read_only, original_path="", **kwargs)

    @classmethod
    @pydantic.validate_call
    @override
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        storage: str | None,
        obj: object,
        metadata: dict[str, object] | None,
        upload_timeout: int | None = None,
        allow_pickling: bool = True,
        offline: bool = False,
        **kwargs: object,
    ) -> Self:
        """Create a new artifact either locally or on the server.

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
        upload_timeout : int | None, optional
            specify the timeout in seconds for upload
        allow_pickling : bool, optional
            whether to allow the object to be pickled if no other
            serialization found. Default is True
        offline : bool, optional
            whether to define this artifact locally, default is False

        """
        # If the object has been saved as a bytes file, obj will be None
        if obj is None:
            try:
                _data_type = kwargs.pop("mime_type")
                _serialized = kwargs.pop("serialized")
                _checksum = kwargs.pop("checksum")
                _ = kwargs.pop("size")
                _ = kwargs.pop("original_path")
            except KeyError as e:
                raise ValueError("Must provide an object to be saved, not None.") from e

        else:
            _serialization = serialize_object(obj, allow_pickling)

            if not _serialization or not (_serialized := _serialization[0]):
                _out_msg: str = f"Could not serialize object of type '{type(obj)}'"
                raise ValueError(_out_msg)

            if not (_data_type := _serialization[1]) and not allow_pickling:
                _out_msg = (
                    f"Could not serialize object of type '{type(obj)}' without pickling"
                )
                raise ValueError(_out_msg)

            _checksum = calculate_sha256(_serialized, is_file=False)

        _serialized = typing.cast("ReadableBuffer", _serialized)

        _artifact = cls(
            identifier=None,
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
            _artifact._staging["obj"] = None
            _artifact._local_staging_file.parent.mkdir(parents=True, exist_ok=True)
            _file_path: pathlib.Path = _artifact._local_staging_file.parent.joinpath(
                f"{_artifact.id}.object"
            )
            with _file_path.open("wb") as file:
                _ = file.write(_serialized)

        else:
            _single_post_data = typing.cast(
                "dict[str, dict[str, object]]",
                _artifact._post_single(**_artifact._staging),
            )
            _artifact._init_data = _single_post_data
            _artifact._staging["url"] = _artifact._init_data["url"]

        _artifact._init_data["runs"] = typing.cast(
            "dict[str, object]", kwargs.get("runs") or {}
        )

        if offline:
            return _artifact

        _file_data = io.BytesIO(_serialized)

        _artifact._upload(
            file=_file_data,
            timeout=upload_timeout,
            file_size=len(_file_data.getbuffer()),
        )
        return _artifact
