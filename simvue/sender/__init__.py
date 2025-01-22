# Collator
import json
import pathlib
import pydantic
import typing
from simvue.api.objects.base import SimvueObject
from simvue.api.objects.storage.file import FileStorage

UPLOAD_ORDER: tuple[str, ...] = (
    "tenants",
    "users",
    "storage",
    "folders",
    "tags",
    "alerts",
    "runs",
    "artifacts",
)


@pydantic.validate_call
def _check_local_staging(cache_dir: pydantic.DirectoryPath) -> None:
    """Check local cache and assemble any objects for sending"""
    _upload_data: dict[str, dict[str, typing.Any]] = {}
    for obj_type in UPLOAD_ORDER:
        _cache_files: list[pathlib.Path] = cache_dir.glob(f"{obj_type}/*.json")
        _upload_data[obj_type] = {
            _path.name.split(".")[0]: json.load(_path.open()) for _path in _cache_files
        }
    return _upload_data


# Create instances from local cache
# We have to link created IDs to other objects
def _assemble_objects(
    locally_staged: dict[str, dict[str, typing.Any]],
) -> typing.Generator[SimvueObject, None, None]:
    for obj_type, data in locally_staged.items():
        if obj_type == "storage" and data.pop("type") == "File":
            FileStorage.new(**data)


# Rather than a script with API calls each object will send itself
