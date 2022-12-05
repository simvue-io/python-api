import glob
import json
import logging
import os
import shutil
import time

import msgpack

from .remote import Remote
from .utilities import get_offline_directory, create_file, remove_file

logger = logging.getLogger(__name__)

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
    if name:
        if 'name' in data:
            if not data['name']:
                data['name'] = name
        else:
            for item in data:
                if 'run' in item:
                    if not item['run']:
                        item['run'] = name
    return data

def sender():
    """
    Asynchronous upload of runs to Simvue server
    """
    directory = get_offline_directory()

    # Deal with runs in the created, running or a terminal state
    runs = glob.glob(f"{directory}/*/created") + \
           glob.glob(f"{directory}/*/running") + \
           glob.glob(f"{directory}/*/completed") + \
           glob.glob(f"{directory}/*/failed") + \
           glob.glob(f"{directory}/*/terminated")

    for run in runs:
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

        current = run.replace('/running', '').replace('/completed', '').replace('/failed', '').replace('/terminated', '').replace('/created', '')

        if os.path.isfile("f{current}/sent"):
            if status == 'running':
                remove_file(f"{current}/running")
            elif status == 'completed':
                remove_file(f"{current}/completed")
            elif status == 'failed':
                remove_file(f"{current}/failed")
            elif status == 'terminated':
                remove_file(f"{current}/terminated")
            elif status == 'created':
                remove_file(f"{current}/created")
            continue

        id = run.split('/')[len(run.split('/')) - 2]

        run_init = get_json(f"{current}/run.json")
        start_time = os.path.getctime(f"{current}/run.json")

        logger.info('Considering run with name %s and id %s', run_init['name'], id)

        remote = Remote(run_init['name'], id, suppress_errors=True)

        # Check token
        remote.check_token()

        # Create run if it hasn't previously been created
        created_file = f"{current}/init"
        name = None
        if not os.path.isfile(created_file):
            name = remote.create_run(run_init)
            logger.info('Creating run with name %s', run_init['name'])
            run_init = add_name(name, run_init, f"{current}/run.json")
            create_file(created_file)

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
            logger.info('Changing status to lost, name %s and id %s', run_init['name'], id)
            status = 'lost'
            create_file(f"{current}/lost")
            remove_file(f"{current}/running")

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

            # Handle metrics
            if '/metrics-' in record:
                logger.info('Sending metrics for run %s', run_init['name'])
                remote.send_metrics(msgpack.packb(get_json(record, name), use_bin_type=True))
                rename = True

            # Handle events
            if '/event-' in record:
                logger.info('Sending event for run %s', run_init['name'])
                remote.send_event(msgpack.packb(get_json(record, name), use_bin_type=True))
                rename = True

            # Handle updates
            if '/update-' in record:
                logger.info('Sending update for run %s', run_init['name'])
                remote.update(get_json(record, name))
                rename = True

            # Handle folders
            if '/folder-' in record:
                logger.info('Sending folder details for run %s', run_init['name'])
                remote.set_folder_details(get_json(record, name))
                rename = True

            # Handle alerts
            if '/alert-' in record:
                logger.info('Sending alert details for run %s', run_init['name'])
                remote.add_alert(get_json(record, name))
                rename = True

            # Handle files
            if '/file-' in record:
                logger.info('Saving file for run %s', run_init['name'])
                remote.save_file(get_json(record, name))
                rename = True

            # Rename processed files
            if rename:
                os.rename(record, f"{record}-proc")
                updates += 1

        # If the status is completed and there were no updates, the run must have completely finished
        if updates == 0 and status in ('completed', 'failed', 'terminated'):
            logger.info('Finished sending run %s', run_init['name'])
            create_file(f"{current}/sent")
            remove_file(f"{current}/{status}")
            data = {'name': run_init['name'], 'status': status}
            remote.update(data)
            cleanup = True
        elif updates == 0 and status == 'lost':
            logger.info('Finished sending run %s as it was lost', run_init['name'])
            create_file(f"{current}/sent")
            cleanup = True

        # Cleanup runs which have been dealt with
        if cleanup:
            try:
                shutil.rmtree(f"{directory}/{id}")
            except Exception as err:
                logger.err('Got exception trying to cleanup run %s: %s', run_init['name'], str(err))
