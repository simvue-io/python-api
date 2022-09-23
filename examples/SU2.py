import csv
import os
import sys
import time
    
from simvue import Simvue

if __name__ == "__main__":
    # Name of history file to collect metrics from
    HISTORY = 'history.csv'
    
    # Check the history file for new entries at this interval (in secs)
    POLLING_INTERVAL = 5
    
    # Store these input files
    INPUT_FILES = ['inv_ONERAM6.cfg', 'mesh_ONERAM6_inv_ffd.su2']
    
    # Store these output files
    OUTPUT_FILES = ['flow.vtu', 'surface_flow.vtu', 'restart_flow.dat']
    
    # Collect these metadata attributes from the config file
    METADATA_ATTRS = ['SOLVER', 'MATH_PROBLEM', 'MACH_NUMBER', 'AOA', 'SIDESLIP_ANGLE', 'FREESTREAM_PRESSURE', 'FREESTREAM_TEMPERATURE']
    
    # Get PID of SU2
    with open(sys.argv[1], 'r') as fh:
        pid = int(fh.read())
    
    # Read metadata
    metadata = {}
    for filename in INPUT_FILES:
        if filename.endswith('.cfg'):
            with open(filename, 'r') as cfg:
                for line in cfg.readlines():
                    for attr in METADATA_ATTRS:
                        if line.startswith(attr):
                            metadata[attr] = line.split('%s= ' % attr)[1].strip()
    
    run = Simvue()
    run.init(metadata=metadata, tags=['SU2'],
             description='SU2 tutorial https://su2code.github.io/tutorials/Inviscid_ONERAM6/')
    
    # Save input files
    for input_file in INPUT_FILES:
        filetype = None
        if input_file.endswith('.cfg'):
            filetype = 'text/plain'
        run.save(input_file, 'input', filetype)
    
    running = True
    latest = []
    first = True
    cols = []
    
    while running:
        # If history.csv doesn't exist yet, wait for it
        if not os.path.isfile(HISTORY):
            time.sleep(POLLING_INTERVAL)
            continue
    
        # Read history.csv and get the latest rows
        header = []
        with open(HISTORY, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter = ',')
            new_rows = False
            for row in csv_reader:
                if not header:
                    header = [item.strip().replace('"', '') for item in row]
                    col = 0
                    for item in header:
                        item = item.strip().replace('"', '')
                        if 'rms' in item:
                            cols.append(col)
                        col += 1
                else:
                    if new_rows or not latest:
                        metrics = {}
                        for i in range(0, len(cols)):
                            data = row[cols[i]].strip().replace('"', '')
                            metrics[header[cols[i]]] = data
                        run.log_metrics(metrics)
                            
                if row == latest:
                    new_rows = True
                
            latest = row
    
        # Check if application is still running
        try:
            os.kill(pid, 0)
        except OSError:
            running = False
        else:
            time.sleep(POLLING_INTERVAL)
    
    # Save output files
    for output_file in OUTPUT_FILES:
        run.save(output_file, 'output' )
    
    run.close()
