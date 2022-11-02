import glob
import json
import os
import tinydb

from .remote import Remote
from .utilities import get_offline_directory

def get_json(filename):
    """
    Get JSON from a file
    """
    with open(filename, 'r') as fh:
        data = json.load(fh)
    return data

def get_binary(filename):
    """
    Get binary content from a file
    """
    with open(filename, 'rb') as fh:
        data = fh.read()
    return data

def sender():
    """
    Asynchronous upload of runs to Simvue server
    """
    db = tinydb.TinyDB(os.path.join(os.path.expanduser("~"), '.simvue.json'))
    existing = db.all()
    directory = get_offline_directory()

    # Deal with runs in the running or completed state
    runs = glob.glob(f"{directory}/*/running") + glob.glob(f"{directory}/*/completed")
    for run in runs:
        status = None
        if run.endswith('running'):
            status = 'running'
        elif run.endswith('completed'):
            status = 'completed'

        current = run.replace('/running', '')
        current = run.replace('/completed', '')

        id = run.split('/')[len(run.split('/')) - 2]

        Run = tinydb.Query()
        results = db.search(Run.id == id)
        run_init = get_json(f"{current}/run.json")

        remote = Remote(run_init['name'], suppress_errors=True)

        # Create run if it hasn't previously been created
        if not results:
            db.insert({'id': id, 'status': status})
            remote.create_run(run_init)
        
        # Send heartbeat if necessary
        if status == 'running':
            remote.send_heartbeat()
          
        # Upload metrics, events, files & metadata as necessary
        files = sorted(glob.glob(f"{current}/*"), key=os.path.getmtime)
        for record in files:
            if record.endswith('/run.json') or \
               record.endswith('/running') or \
               record.endswith('/completed') or \
               record.endswith('-proc'):
                continue

            rename = False

            # Handle metrics
            if '/metrics-' in record:
                remote.send_metrics(get_binary(record))
                rename = True

            # Handle events
            if '/event-' in record:
                remote.send_event(get_binary(record))
                rename = True

            # Handle updates
            if '/update-' in record:
                remote.update(get_json(record))
                rename = True

            # Handle folders
            if '/folder-' in record:
                remote.set_folder_details(get_json(record))
                rename = True

            # Handle alerts
            if '/alert-' in record:
                remote.add_alert(get_json(record))
                rename = True

            # Handle files
            if '/file-' in record:
                remote.save_file(get_json(record))
                rename = True

            # Rename processed files
            if rename:
                os.rename(record, f"{record}-proc")

            # Check if finished
            if record.endswith('/completed'):
                db.update({'status': 'completed'}, Run.id == id)

    # Deal with runs in the completed state
    runs = glob.glob(f"{directory}/*/completed")
    for run in runs:
        id = run.split('/')[len(run.split('/')) - 2]
        Run = tinydb.Query()
        results = db.search(Run.id == id)
        if results:
            status = results[0]['status']
            if status != 'completed':
                db.update({'status': 'completed'}, Run.id == id)
