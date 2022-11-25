# PyTorch

This example is based on the Medium post https://medium.com/optuna/optuna-meets-weights-and-biases-58fc6bab893.

> We optimize the validation accuracy of hand-written
> digit recognition using
> PyTorch and FashionMNIST. We optimize the neural network architecture as well as the optimizer
> configuration. As it is too time consuming to use the whole FashionMNIST dataset,
> we here use a small subset of it.

Setup a virtual environment:
```
python3 -m venv venv
source ./venv/bin/activate
```
Install the required dependencies:
```
pip install -r requirements.txt 
```
Run the code:
```
python3 simvue_optuna_pytorch.py
```
By default this will create 100 runs in Simvue, all in a folder with name `/optuna/tests/<adjective>-<noun>`, where `<adjective>` is a random
adjective and `<noun>` is a random noun.
