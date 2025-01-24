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


def _check_local_staging(
    cache_dir: pathlib.Path,
) -> dict[str, dict[pathlib.Path, dict[str, typing.Any]]]:
    """Check local cache and assemble any objects for sending"""
    _upload_data: dict[str, dict[pathlib.Path, dict[str, typing.Any]]] = {
        obj_type: {
            _path: json.load(_path.open())
            for _path in cache_dir.glob(f"{obj_type}/*.json")
        }
        for obj_type in UPLOAD_ORDER
    }
    return _upload_data


# Create instances from local cache
# We have to link created IDs to other objects
def _assemble_objects(
    locally_staged: dict[str, dict[pathlib.Path, typing.Any]],
) -> typing.Generator[tuple[pathlib.Path, SimvueObject], None, None]:
    for obj_type in UPLOAD_ORDER:
        _data: dict[pathlib.Path, dict[str, typing.Any]] = locally_staged.get(
            obj_type, {}
        )
        for _file_path, _obj in _data.items():
            _exact_type: str = _obj.pop("obj_type")
            try:
                _instance_class: SimvueObject = getattr(simvue.api.objects, _exact_type)
            except AttributeError as e:
                raise RuntimeError(
                    f"Attempt to initialise unknown type '{_exact_type}'"
                ) from e
            yield _file_path, _instance_class.new(**_obj)


# Rather than a script with API calls each object will send itself
@prettify_pydantic
@pydantic.validate_call
def uploader(
    cache_dir: pydantic.DirectoryPath, _offline_ids: list[str] | None = None
) -> typing.Generator[tuple[str, SimvueObject], None, None]:
    _locally_staged = _check_local_staging(cache_dir)
    _offline_to_online_id_mapping: dict[str, str] = {}
    for _file_path, obj in _assemble_objects(_locally_staged):
        if _offline_ids and obj._identifier not in _offline_ids:
            continue

        if not (_current_id := obj._identifier):
            raise RuntimeError(
                f"Object of type '{obj.__class__.__name__}' has no identifier"
            )
        try:
            obj.commit()
            _new_id = obj.id
        except RuntimeError as e:
            if "status 409" in e.args[0]:
                continue
            raise e
        if not _new_id:
            raise RuntimeError(
                f"Object of type '{obj.__class__.__name__}' has no identifier"
            )
        _logger.info(f"Created {obj.__class__.__name__} '{_new_id}'")
        _file_path.unlink(missing_ok=True)
        _offline_to_online_id_mapping[_current_id] = _new_id
        obj.on_reconnect(_offline_to_online_id_mapping)
        yield _current_id, obj
