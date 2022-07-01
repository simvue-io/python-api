# Simulation management &amp; observability

## Usage example
```
from obversability import Observability

...

run = Observability()

# Specify name, metadata, and optional tags
run.init('example-run-name', {'learning_rate': 0.001,
         'training_steps': 2000, 'batch_size': 32}, ['tensorflow'])

# Upload an input file, code etc
run.save('training.py')

...

while True:

...

    # Send metrics
    run.log({'loss': 0.5, 'density': 34.4})

...

# Upload an output file
run.save('output.h5')
```
