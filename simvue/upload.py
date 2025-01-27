# Collator
import json
import pydantic
import logging
import typing
from simvue.api.objects.base import SimvueObject

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
    "metrics",
    "events",
)

_logger = logging.getLogger(__name__)


# Rather than a script with API calls each object will send itself
@pydantic.validate_call
def uploader(
    cache_dir: pydantic.DirectoryPath, _offline_ids: list[str] | None = None
) -> typing.Generator[tuple[str, SimvueObject], None, None]:
    cache_dir.joinpath("server_ids").mkdir(parents=True, exist_ok=True)
    _id_mapping: dict[str, str] = {
        file_path.name.split(".")[0]: file_path.read_text()
        for file_path in cache_dir.glob("server_ids/*.txt")
    }

    for obj_type in UPLOAD_ORDER:
        for file_path in cache_dir.glob(f"{obj_type}/*.json"):
            _current_id = file_path.name.split(".")[0]
            data = json.load(file_path.open())
            _exact_type: str = data.pop("obj_type")
            try:
                _instance_class: SimvueObject = getattr(simvue.api.objects, _exact_type)
            except AttributeError as e:
                raise RuntimeError(
                    f"Attempt to initialise unknown type '{_exact_type}'"
                ) from e
            # We want to reconnect if there is an online ID stored for this file
            obj_for_upload = _instance_class.new(
                identifier=_id_mapping.get(_current_id, None), **data
            )
            obj_for_upload.on_reconnect(_id_mapping)

            try:
                obj_for_upload.commit()
                _new_id = obj_for_upload.id
            except RuntimeError as e:
                if "status 409" in e.args[0]:
                    continue
                raise e
            if not _new_id:
                raise RuntimeError(
                    f"Object of type '{obj_for_upload.__class__.__name__}' has no identifier"
                )
            if _id_mapping.get(_current_id, None):
                _logger.info(f"Updated {obj_for_upload.__class__.__name__} '{_new_id}'")
            else:
                _logger.info(f"Created {obj_for_upload.__class__.__name__} '{_new_id}'")
            file_path.unlink(missing_ok=True)
            _id_mapping[_current_id] = _new_id
            if obj_type == "runs":
                cache_dir.joinpath("server_ids", f"{_current_id}.txt").write_text(
                    _new_id
                )

                if cache_dir.joinpath(f"{obj_type}", f"{_current_id}.closed").exists():
                    cache_dir.joinpath("server_ids", f"{_current_id}.txt").unlink()
                    cache_dir.joinpath(f"{obj_type}", f"{_current_id}.closed").unlink()
                    _logger.info(
                        f"Run {_current_id} closed - deleting cached copies..."
                    )
