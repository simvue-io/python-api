# PyTorch

This is an example of using Simvue to track and monitor the training of a Machine Learning model using PyTorch.

To run this example, move into this directory:
```
cd examples/PyTorch
```
Setup a virtual environment:
```
python3 -m venv venv
source ./venv/bin/activate
```
Install the required dependencies:
```
pip install -r requirements.txt
```
Create a `simvue.toml` file by going to the web UI, clicking 'Create New Run', and copying the details given into the file, eg using:
```
nano simvue.toml
```
Run the code:
```
python3 main.py
```
