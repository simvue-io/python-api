# Logging
You can use Simvue as a logging handler, so that you can easily upload logging messages to the Events log of a Simvue run.

To run this example, move into this directory:
```
cd examples/Logging
```
Setup a virtual environment:
```
python3 -m venv venv
source ./venv/bin/activate
```
Install the required dependencies:
```
pip install simvue
```
Create a `simvue.toml` file by going to the web UI, clicking 'Create New Run', and copying the details given into the file, eg using:
```
nano simvue.toml
```
Run the code:
```
python3 logging-to-simvue.py
```