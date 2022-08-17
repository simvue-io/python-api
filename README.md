# Simulation tracking &amp; monitoring

_This is a PoC, and the name is temporary!_

## Configuration
The service URL and token can be defined as environment variables:
```
export SIMTRACK_URL=...
export SIMTRACK_TOKEN=...
```
or a file `simtrack.ini` can be created containing:
```
[server]
url = ...
token = ...
```

## Usage example
```
from simtrack import Simtrack

...

# Using a context manager means that the status will be set to completed automatically
with Simtrack() as run:

    # Specify a run name, metadata (dict), tags (list), description, folder
    run.init('example-run-name',
             {'learning_rate': 0.001, 'training_steps': 2000, 'batch_size': 32}, # metadaata
             ['tensorflow'],                                                     # tags
	     'This is a test.',                                                 # description
	     '/Project-A/part1')                                                # folder
 
    # Upload the code
    run.save('training.py', 'code')

    # Upload an input file
    run.save('params.in', 'input')

    # Add an alert (the alert definition will be created if necessary)
    run.add_alert('loss-too-high', # Name
                 'is above',       # Type
                 'loss',           # Metric
                 1,                # Frequency
                 1,                # Window
                 threshold=10)     # Threshold

    ...

    while not converged:

        ...

        # Send metrics inside main application loop
        run.log({'loss': 0.5, 'density': 34.4})

    # Upload an output file
    run.save('output.cdf', 'output')
```
