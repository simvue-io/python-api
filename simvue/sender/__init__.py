# Collator
import json
import pathlib
import pydantic
import logging
import typing
from simvue.api.objects.base import SimvueObject
from simvue.utilities import prettify_pydantic
import simvue.api.objects

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

_logger = logging.getLogger(__name__)


def _check_local_staging(cache_dir: pathlib.Path) -> None:
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
    for obj_type in UPLOAD_ORDER:
        _data = locally_staged.get(obj_type, {})
        for _local_id, _obj in _data.items():
            _exact_type: str = _obj.pop("obj_type")
            try:
                _instance_class = getattr(simvue.api.objects, _exact_type)
            except AttributeError as e:
                raise RuntimeError(
                    f"Attempt to initialise unknown type '{_exact_type}'"
                ) from e
            yield _instance_class.new(**_obj)


# Rather than a script with API calls each object will send itself
@prettify_pydantic
@pydantic.validate_call
def uploader(cache_dir: pydantic.DirectoryPath) -> None:
    _locally_staged = _check_local_staging(cache_dir)
    _offline_to_online_id_mapping: dict[str, str] = {}
    for obj in _assemble_objects(_locally_staged):
        _current_id = obj._identifier
        try:
            obj.commit()
            _logger.info(f"Created {obj.__class__.__name__} '{obj.id}'")
        except RuntimeError as e:
            if "status 409" in e.args[0]:
                continue
            else:
                raise e
        _offline_to_online_id_mapping[_current_id] = obj.id
