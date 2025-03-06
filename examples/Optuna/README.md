# PyTorch

This example is based on the Medium post https://medium.com/optuna/optuna-meets-weights-and-biases-58fc6bab893.

> We optimize the validation accuracy of hand-written
> digit recognition using
> PyTorch and FashionMNIST. We optimize the neural network architecture as well as the optimizer
> configuration. As it is too time consuming to use the whole FashionMNIST dataset,
> we here use a small subset of it.

To run this example, move into this directory:
```
cd examples/Optuna
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
python3 simvue_optuna_pytorch.py
```
By default this will create a number runs in Simvue, all in a folder with name `/optuna/tests/<adjective>-<noun>`, where `<adjective>` is a random
adjective and `<noun>` is a random noun. Metadata and a metric `validation accuracy` is collected during each run. The metadata includes
an attribute `state` which indicates if the run completed successfully or was pruned.
