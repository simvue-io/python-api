import glob
import json
import logging
import os
import shutil
import typing
import flatdict
import time

import msgpack

from .factory.remote import Remote
from .utilities import get_offline_directory, create_file, remove_file

logger = logging.getLogger(__name__)

def update_name(name, data):
    """
    Update name in metrics/events
    """
    flat_data = flatdict.FlatDict(data)
    for label in flat_data.keys():
        if any([
            label == "run",
            len(_split_label := label.split(":")) > 1 and
            _split_label[-1] == "run"
        ]):
            flat_data[label] = name
    return flat_data.as_dict()

def add_name(name, data, filename):
    """
    Update name in JSON
    """
    if not data['name']:
        data['name'] = name
        with open(filename, 'w') as fh:
            json.dump(data, fh)

    return data

def get_json(filename, name=None):
    """
    Get JSON from a file
    """
    with open(filename, 'r') as fh:
        data = json.load(fh)

    if not name:
        return data


    if 'name' in data and not data['name']:
        data['name'] = name
        return data
    
    return update_name(name, data)


def sender(suppress_errors: bool=True) -> list[str]:
    """
    Asynchronous upload of runs to Simvue server
    """
    directory = get_offline_directory()

    logger.debug(f"Finding runs in directory '{directory}'")

    # Deal with runs in the created, running or a terminal state
    runs = glob.glob(f"{directory}/*/created") + \
           glob.glob(f"{directory}/*/running") + \
           glob.glob(f"{directory}/*/completed") + \
           glob.glob(f"{directory}/*/failed") + \
           glob.glob(f"{directory}/*/terminated")
    
    if not runs:
        logger.warning("Sender called but no runs to upload.")
        return []

    upload_run_ids: list[str] = []

    for run in runs:
        run_id: str | None = None
        cleanup = False
        status = None
        if run.endswith('running'):
            status = 'running'
        if run.endswith('created'):
            status = 'created'
        elif run.endswith('completed'):
            status = 'completed'
        elif run.endswith('failed'):
            status = 'failed'
        elif run.endswith('terminated'):
            status = 'terminated'

        current = run.replace('/running', '').\
                  replace('/completed', '').\
                  replace('/failed', '').\
                  replace('/terminated', '').\
                  replace('/created', '')

        if os.path.isfile(f"{current}/sent"):
            if status == 'running':
                remove_file(f"{current}/running", suppress_errors)
            elif status == 'completed':
                remove_file(f"{current}/completed", suppress_errors)
            elif status == 'failed':
                remove_file(f"{current}/failed", suppress_errors)
            elif status == 'terminated':
                remove_file(f"{current}/terminated", suppress_errors)
            elif status == 'created':
                remove_file(f"{current}/created", suppress_errors)
            continue

        unique_identifier = run.split('/')[len(run.split('/')) - 2]

        if not os.path.exists((_run_file := os.path.join(current, "run.json"))):
            raise FileNotFoundError(
                f"Failed to initialise run from sender, file '{_run_file}' not found"
            )

        run_init = get_json(_run_file)
        start_time = os.path.getctime(_run_file)

        if run_init['name']:
            logger.info('Considering run with name %s and id %s', run_init['name'], unique_identifier)
        else:
            logger.info('Considering run with no name yet and id %s', unique_identifier)

        remote = Remote(run_init['name'], unique_identifier, suppress_errors=suppress_errors)

        # Check token
        remote.check_token()

        # Create run if it hasn't previously been created
        created_file = f"{current}/init"
        name = None
        if not os.path.isfile(created_file):
            name, run_id = remote.create_run(run_init)
            if name:
                if not current or not os.path.exists(directory):
                    raise FileNotFoundError("No directory defined for writing")
                logger.info('Creating run with name %s', name)
                run_init = add_name(name, run_init, _run_file)
                with open(created_file, "w") as out_f:
                    out_f.write(run_id)
                if not run_id:
                    logger.error(f"Failed to retrieve a run ID for '{name}'")
                    continue
                upload_run_ids.append(run_id)
            else:
                logger.error('Failure creating run')
                continue
        else:
            logger.debug("Retrieving ID from existing run file")
            run_id = open(created_file).read().strip()
            upload_run_ids.append(run_id)

        if status == 'running':
            # Check for recent heartbeat
            heartbeat_filename = f"{current}/heartbeat"
            if os.path.isfile(heartbeat_filename):
                mtime = os.path.getmtime(heartbeat_filename)
                if time.time() - mtime > 180:
                    status = 'lost'

            # Check for no recent heartbeat
            if not os.path.isfile(heartbeat_filename):
                if time.time() - start_time > 180:
                    status = 'lost'

        # Handle lost runs
        if status == 'lost':
            logger.info('Changing status to lost, name %s and id %s', run_init['name'], unique_identifier)
            status = 'lost'
            create_file(f"{current}/lost")
            remove_file(f"{current}/running", suppress_errors)

        # Send heartbeat if the heartbeat file was touched recently
        if status == 'running' and time.time() - os.path.getmtime(heartbeat_filename) < 120:
            logger.info('Sending heartbeat for run with name %s', run_init['name'])
            remote.send_heartbeat()

        # Upload metrics, events, files & metadata as necessary
        files = sorted(glob.glob(f"{current}/*"), key=os.path.getmtime)
        updates = 0
        for record in files:
            if record.endswith('/run.json') or \
               record.endswith('/running') or \
               record.endswith('/completed') or \
               record.endswith('/failed') or \
               record.endswith('/terminated') or \
               record.endswith('/lost') or \
               record.endswith('/sent') or \
               record.endswith('-proc'):
                continue

            rename = False

            updatable_record_types: tuple[str, ...] = (
                "metrics",
                "events",
                "update",
                "folder",
                "alert",
                "file"
            )

            if (
                not rename and
                not any(f"/{i}" in record for i in updatable_record_types)
            ):
                continue

            if not rename:
                try:
                    _json_data: dict = get_json(record, name)
                    _json_data["id"] = run_id
                except TypeError as e:
                    raise TypeError(f"Failed to parse '{name}' in '{record}': {e}")

            # Handle metrics
            if '/metrics-' in record:
                logger.info('Sending metrics for run %s with record: %s', run_init['name'], _json_data)
                update_name(run_init['name'], _json_data)
                if remote.send_metrics(msgpack.packb(_json_data, use_bin_type=True)):
                    rename = True

            # Handle events
            elif '/events-' in record:
                logger.info('Sending events for run %s with record: %s', run_init['name'], _json_data)
                update_name(run_init['name'], _json_data)
                if remote.send_event(msgpack.packb(_json_data, use_bin_type=True)):
                    rename = True

            # Handle updates
            elif '/update-' in record:
                logger.info('Sending update for run %s with record: %s', run_init['name'], _json_data)
                
                if (_name := run_init.get("name")):
                    _json_data["run"] =  _name
                
                if remote.update(_json_data):
                    rename = True

            # Handle folders
            elif '/folder-' in record:
                logger.info('Sending folder details for run %s with record: %s', run_init['name'], _json_data)
                
                if (_name := run_init.get("name")):
                    _json_data["run"] =  _name
                
                if remote.set_folder_details(_json_data):
                    rename = True

            # Handle alerts
            elif '/alert-' in record:
                logger.info('Sending alert details for run %s with record: %s', run_init['name'], _json_data)
                
                if (_name := run_init.get("name")):
                    _json_data["run"] =  _name

                if remote.add_alert(_json_data):
                    rename = True

            # Handle files
            elif '/file-' in record:
                logger.info('Saving file for run %s with record: %s', run_init['name'], _json_data)
                
                if (_name := run_init.get("name")):
                    _json_data["run"] =  _name
                
                if remote.save_file(_json_data):
                    rename = True

            # Rename processed files
            elif rename:
                os.rename(record, f"{record}-proc")
                updates += 1

        # If the status is completed and there were no updates, the run must have completely finished
        if updates == 0 and status in ('completed', 'failed', 'terminated'):
            logger.info('Finished sending run %s', run_init['name'])
            data = {'name': run_init['name'], 'status': status}
            if remote.update(data):
                create_file(f"{current}/sent")
                remove_file(f"{current}/{status}", suppress_errors)
                cleanup = True
        elif updates == 0 and status == 'lost':
            logger.info('Finished sending run %s as it was lost', run_init['name'])
            create_file(f"{current}/sent")
            cleanup = True

        # Cleanup runs which have been dealt with
        if cleanup:
            try:
                shutil.rmtree(f"{directory}/{unique_identifier}")
            except Exception as err:
                logger.error('Got exception trying to cleanup run %s: %s', run_init['name'], str(err))

        return upload_run_ids
