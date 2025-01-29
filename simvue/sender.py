"""
Simvue Sender
==============

Function to send data cached by Simvue in Offline mode to the server.
"""

import json
import pydantic
import logging
from concurrent.futures import ThreadPoolExecutor
import threading
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


def upload_cached_file(
    cache_dir: pydantic.DirectoryPath,
    obj_type: str,
    file_path: pydantic.FilePath,
    id_mapping: dict[str, str],
    lock: threading.Lock,
):
    """Upload data stored in a cached file to the Simvue server.

    Parameters
    ----------
    cache_dir : pydantic.DirectoryPath
        The directory where cached files are stored
    obj_type : str
        The type of object which should be created for this cached file
    file_path : pydantic.FilePath
        The path to the cached file to upload
    id_mapping : dict[str, str]
        A mapping of offline to online object IDs
    lock : threading.Lock
        A lock to prevent multiple threads accessing the id mapping directory at once
    """
    _current_id = file_path.name.split(".")[0]
    _data = json.load(file_path.open())
    _exact_type: str = _data.pop("obj_type")
    try:
        _instance_class: SimvueObject = getattr(simvue.api.objects, _exact_type)
    except AttributeError as e:
        raise RuntimeError(f"Attempt to initialise unknown type '{_exact_type}'") from e
    # We want to reconnect if there is an online ID stored for this file
    obj_for_upload = _instance_class.new(
        identifier=id_mapping.get(_current_id, None), **_data
    )
    with lock:
        obj_for_upload.on_reconnect(id_mapping)

    try:
        obj_for_upload.commit()
        _new_id = obj_for_upload.id
    except RuntimeError as error:
        if "status 409" in error.args[0]:
            return
        raise error
    if not _new_id:
        raise RuntimeError(
            f"Object of type '{obj_for_upload.__class__.__name__}' has no identifier"
        )
    if id_mapping.get(_current_id, None):
        _logger.info(f"Updated {obj_for_upload.__class__.__name__} '{_new_id}'")
    else:
        _logger.info(f"Created {obj_for_upload.__class__.__name__} '{_new_id}'")
    file_path.unlink(missing_ok=True)

    with lock:
        id_mapping[_current_id] = _new_id

    if obj_type in ["alerts", "runs"]:
        cache_dir.joinpath("server_ids", f"{_current_id}.txt").write_text(_new_id)

    if (
        obj_type == "runs"
        and cache_dir.joinpath(f"{obj_type}", f"{_current_id}.closed").exists()
    ):
        # Get list of alerts created by this run - their IDs can be deleted
        for id in _data.get("alerts", []):
            cache_dir.joinpath("server_ids", f"{id}.txt").unlink()

        cache_dir.joinpath("server_ids", f"{_current_id}.txt").unlink()
        cache_dir.joinpath(f"{obj_type}", f"{_current_id}.closed").unlink()
        _logger.info(f"Run {_current_id} closed - deleting cached copies...")


@pydantic.validate_call
def sender(
    cache_dir: pydantic.DirectoryPath, max_workers: int, threading_threshold: int
):
    """Send data from a local cache directory to the Simvue server.

    Parameters
    ----------
    cache_dir : pydantic.DirectoryPath
         The directory where cached files are stored
    max_workers : int
        The maximum number of threads to use
    threading_threshold : int
        The number of cached files above which threading will be used
    """
    cache_dir.joinpath("server_ids").mkdir(parents=True, exist_ok=True)
    _id_mapping: dict[str, str] = {
        file_path.name.split(".")[0]: file_path.read_text()
        for file_path in cache_dir.glob("server_ids/*.txt")
    }
    _lock = threading.Lock()

    for _obj_type in UPLOAD_ORDER:
        _offline_files = list(cache_dir.glob(f"{_obj_type}/*.json"))
        if len(_offline_files) < threading_threshold:
            for file_path in _offline_files:
                upload_cached_file(cache_dir, _obj_type, file_path, _id_mapping, _lock)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                _results = executor.map(
                    lambda file_path: upload_cached_file(
                        cache_dir=cache_dir,
                        obj_type=_obj_type,
                        file_path=file_path,
                        id_mapping=_id_mapping,
                        lock=_lock,
                    ),
                    _offline_files,
                )
