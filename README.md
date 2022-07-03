# Simulation tracking &amp; observability

## Configuration
The service URL and token can be defined as environment variables:
```
export OBSERVABILITY_URL=...
export OBSERVABILITY_TOKEN=...
```
or a file `observability.ini` can be created containing:
```
[server]
url = ...
token = ...
```

## Usage example
```
from observability import Observability

...

run = Observability()

# Specify name, metadata, and optional tags
run.init('example-run-name', {'learning_rate': 0.001,
         'training_steps': 2000, 'batch_size': 32}, ['tensorflow'])

# Upload an input file
run.save('training.params', 'input')

...

while True:

...

    # Send metrics
    run.log({'loss': 0.5, 'density': 34.4})

...

# Upload an output file
run.save('output.h5', 'output')
```
