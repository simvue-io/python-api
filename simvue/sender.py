import glob
import json
import logging
import os
import shutil
import time

import msgpack

from .factory.remote import Remote
from .utilities import get_offline_directory, create_file, remove_file

logger = logging.getLogger(__name__)

def set_details(name, id, filename):
    """
    Write name & id to file
    """
    data = {'name': name, 'id': id}
    with open(filename, 'w') as fh:
        json.dump(data, fh)

def get_details(name):
    """
    Get name & id from file
    """
    with open(name) as fh:
        data = json.load(fh)
        return data['name'], data['id']

def update_name(id, data):
    """
    Update id in metrics/events
    """
    for item in data:
        item['id'] = id

def add_name(name, data, filename):
    """
    Update name in JSON
    """
    if not data['name']:
        data['name'] = name
        with open(filename, 'w') as fh:
            json.dump(data, fh)

    return data

def read_json(filename):
    with open(filename, 'r') as fh:
        return json.load(fh)

def get_json(filename, run_id=None, artifact=False):
    """
    Get JSON from a file
    """
    with open(filename, 'r') as fh:
        data = json.load(fh)
    if run_id:
        if artifact:
            for item in data:
                if item == 'run':
                    data[item] = run_id
            return data

        if 'run' in data:
            data['run'] = run_id
        else:
            data['id'] = run_id

    return data

def sender():
    """
    Asynchronous upload of runs to Simvue server
    """
    directory = get_offline_directory()

    # Clean up old runs after waiting 5 mins
    runs = glob.glob(f"{directory}/*/sent")

    for run in runs:
        id = run.split('/')[len(run.split('/')) - 2]
        logger.info('Cleaning up directory with id %s', id)

        if time.time() - os.path.getmtime(run) > 300:
            try:
                shutil.rmtree(f"{directory}/{id}")
            except Exception as err:
                logger.error('Got exception trying to cleanup run in directory %s', id)

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

        current = run.replace('/running', '').\
                  replace('/completed', '').\
                  replace('/failed', '').\
                  replace('/terminated', '').\
                  replace('/created', '')

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

        if run_init['name']:
            logger.info('Considering run with name %s and id %s', run_init['name'], id)
        else:
            logger.info('Considering run with no name yet and id %s', id)

        # Create run if it hasn't previously been created
        created_file = f"{current}/init"
        name = None
        if not os.path.isfile(created_file):
            remote = Remote(run_init['name'], id, suppress_errors=False)

            # Check token
            remote.check_token()

            name, run_id = remote.create_run(run_init)
            if name:
                logger.info('Creating run with name %s and id %s', name, id)
                run_init = add_name(name, run_init, f"{current}/run.json")
                set_details(name, run_id, created_file)
            else:
                logger.error('Failure creating run')
                continue
        else:
            name, run_id = get_details(created_file)
            run_init['name'] = name
            remote = Remote(run_init['name'], run_id, suppress_errors=False)

            # Check token
            remote.check_token()

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
        heartbeat_filename = f"{current}/heartbeat"
        if os.path.isfile(heartbeat_filename):
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
                data = get_json(record, run_id)
                if remote.send_metrics(msgpack.packb(data, use_bin_type=True)):
                    rename = True

            # Handle events
            if '/events-' in record:
                logger.info('Sending events for run %s', run_init['name'])
                data = get_json(record, run_id)
                if remote.send_event(msgpack.packb(data, use_bin_type=True)):
                    rename = True

            # Handle updates
            if '/update-' in record:
                logger.info('Sending update for run %s', run_init['name'])
                data = get_json(record, run_id)
                if remote.update(data):
                    for item in data:
                        if item == "status" and data[item] in ('completed', 'failed', 'terminated'):
                            create_file(f"{current}/sent")
                            remove_file(f"{current}/{status}")
                    rename = True


            # Handle folders
            if '/folder-' in record:
                logger.info('Sending folder details for run %s', run_init['name'])
                if remote.set_folder_details(get_json(record, run_id)):
                    rename = True

            # Handle alerts
            if '/alert-' in record:
                logger.info('Sending alert details for run %s', run_init['name'])
                if remote.add_alert(get_json(record, run_id)):
                    rename = True

            # Handle files
            if '/file-' in record:
                logger.info('Saving file for run %s', run_init['name'])
                if remote.save_file(get_json(record, run_id, True)):
                    rename = True

            # Rename processed files
            if rename:
                os.rename(record, f"{record}-proc")
                updates += 1

        # If the status is completed and there were no updates, the run must have completely finished
        if updates == 0 and status in ('completed', 'failed', 'terminated'):
            logger.info('Finished sending run %s', run_init['name'])
            data = {'id': run_id, 'status': status}
            if remote.update(data):
                create_file(f"{current}/sent")
                remove_file(f"{current}/{status}")
        elif updates == 0 and status == 'lost':
            logger.info('Finished sending run %s as it was lost', run_init['name'])
            create_file(f"{current}/sent")
