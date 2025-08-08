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
import requests
import psutil
from simvue.config.user import SimvueConfiguration

import simvue.api.objects
from simvue.eco.emissions_monitor import CO2Monitor
from simvue.version import __version__

UPLOAD_ORDER: list[str] = [
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
]

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
        _instance_class = getattr(simvue.api.objects, _exact_type)
    except AttributeError as e:
        raise RuntimeError(f"Attempt to initialise unknown type '{_exact_type}'") from e

    # If it is an ObjectArtifact, need to load the object as bytes from a different file
    if issubclass(_instance_class, simvue.api.objects.ObjectArtifact):
        with open(file_path.parent.joinpath(f"{_current_id}.object"), "rb") as file:
            _data["serialized"] = file.read()

    # We want to reconnect if there is an online ID stored for this file
    if _online_id := id_mapping.get(_current_id):
        obj_for_upload = _instance_class(
            identifier=_online_id, _read_only=False, **_data
        )
    else:
        obj_for_upload = _instance_class.new(**_data)

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
    _logger.info(
        f"{'Updated' if id_mapping.get(_current_id) else 'Created'} {obj_for_upload.__class__.__name__} '{_new_id}'"
    )

    file_path.unlink(missing_ok=True)
    if issubclass(_instance_class, simvue.api.objects.ObjectArtifact):
        file_path.parent.joinpath(f"{_current_id}.object").unlink()

    with lock:
        id_mapping[_current_id] = _new_id

    if obj_type in {"alerts", "runs", "folders", "tags"}:
        cache_dir.joinpath("server_ids", f"{_current_id}.txt").write_text(_new_id)

    if (
        obj_type == "runs"
        and cache_dir.joinpath(f"{obj_type}", f"{_current_id}.closed").exists()
    ):
        # Get alerts and folder created by this run - their IDs can be deleted
        for id in _data.get("alerts", []):
            cache_dir.joinpath("server_ids", f"{id}.txt").unlink()
        if _folder_id := _data.get("folder_id"):
            cache_dir.joinpath("server_ids", f"{_folder_id}.txt").unlink()

        cache_dir.joinpath("server_ids", f"{_current_id}.txt").unlink()
        cache_dir.joinpath(f"{obj_type}", f"{_current_id}.closed").unlink()
        _logger.info(f"Run {_current_id} closed - deleting cached copies...")


def send_heartbeat(
    file_path: pydantic.FilePath,
    id_mapping: dict[str, str],
    server_url: str,
    headers: dict[str, str],
):
    _offline_id = file_path.name.split(".")[0]
    _online_id = id_mapping.get(_offline_id)
    if not _online_id:
        # Run has been closed - can just remove heartbeat and continue
        file_path.unlink()
        return
    _logger.info(f"Sending heartbeat to run {_online_id}")
    _response = requests.put(
        f"{server_url}/runs/{_online_id}/heartbeat",
        headers=headers,
    )
    if _response.status_code == 200:
        file_path.unlink()
    else:
        _logger.warning(
            f"Attempting to send heartbeat to run {_online_id} returned status code {_response.status_code}."
        )


@pydantic.validate_call
def sender(
    cache_dir: pydantic.DirectoryPath | None = None,
    max_workers: int = 5,
    threading_threshold: int = 10,
    objects_to_upload: list[str] = UPLOAD_ORDER,
) -> dict[str, str]:
    """Send data from a local cache directory to the Simvue server.

    Parameters
    ----------
    cache_dir : pydantic.DirectoryPath
         The directory where cached files are stored
    max_workers : int
        The maximum number of threads to use
    threading_threshold : int
        The number of cached files above which threading will be used
    objects_to_upload : list[str]
        Types of objects to upload, by default uploads all types of objects present in cache

    Returns
    -------
    id_mapping
        mapping of local ID to server ID
    """
    _user_config: SimvueConfiguration = SimvueConfiguration.fetch()
    cache_dir = cache_dir or _user_config.offline.cache

    cache_dir.joinpath("server_ids").mkdir(parents=True, exist_ok=True)
    _lock_path = cache_dir.joinpath("sender.lock")

    # Check that no other sender is already currently running...
    if _lock_path.exists() and psutil.pid_exists(int(_lock_path.read_text())):
        raise RuntimeError("A sender is already running for this cache!")

    # Create lock file to prevent other senders running while this one isn't finished
    _lock_path.write_text(str(psutil.Process().pid))

    _id_mapping: dict[str, str] = {
        file_path.name.split(".")[0]: file_path.read_text()
        for file_path in cache_dir.glob("server_ids/*.txt")
    }
    _lock = threading.Lock()
    _upload_order = [item for item in UPLOAD_ORDER if item in objects_to_upload]
    # Glob all files to look in at the start, to prevent extra files being written while other types are being uploaded
    _all_offline_files = {
        obj_type: list(cache_dir.glob(f"{obj_type}/*.json"))
        for obj_type in _upload_order
    }

    for _obj_type in _upload_order:
        _offline_files = _all_offline_files[_obj_type]
        if len(_offline_files) < threading_threshold:
            for file_path in _offline_files:
                upload_cached_file(cache_dir, _obj_type, file_path, _id_mapping, _lock)
        else:
            with ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="sender_session_upload"
            ) as executor:
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

    # Send heartbeats
    _headers: dict[str, str] = {
        "Authorization": f"Bearer {_user_config.server.token.get_secret_value()}",
        "User-Agent": f"Simvue Python client {__version__}",
    }
    _heartbeat_files = list(cache_dir.glob("runs/*.heartbeat"))
    if len(_heartbeat_files) < threading_threshold:
        for _heartbeat_file in _heartbeat_files:
            (
                send_heartbeat(
                    file_path=_heartbeat_file,
                    id_mapping=_id_mapping,
                    server_url=_user_config.server.url,
                    headers=_headers,
                ),
            )
    else:
        with ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="sender_heartbeat"
        ) as executor:
            _results = executor.map(
                lambda _heartbeat_file: send_heartbeat(
                    file_path=_heartbeat_file,
                    id_mapping=_id_mapping,
                    server_url=_user_config.server.url,
                    headers=_headers,
                ),
                _heartbeat_files,
            )

    # If CO2 emissions are requested create a dummy monitor which just
    # refreshes the CO2 intensity value if required. No emission metrics
    # will be taken by the sender itself, values are assumed to be recorded
    # by any offline runs being sent.
    if _user_config.metrics.enable_emission_metrics:
        CO2Monitor(
            thermal_design_power_per_gpu=None,
            thermal_design_power_per_cpu=None,
            local_data_directory=cache_dir,
            intensity_refresh_interval=_user_config.eco.intensity_refresh_interval,
            co2_intensity=_user_config.eco.co2_intensity,
            co2_signal_api_token=_user_config.eco.co2_signal_api_token,
        ).check_refresh()

    # Remove lock file to allow another sender to start in the future
    _lock_path.unlink()
    return _id_mapping
