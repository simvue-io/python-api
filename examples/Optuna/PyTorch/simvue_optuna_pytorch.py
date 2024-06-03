"""
The main code is based on https://github.com/optuna/optuna-examples/blob/63fe36db4701d5b230ade04eb2283371fb2265bf/pytorch/pytorch_simple.py
"""

import os
import click

import optuna
import randomname
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data
from torchvision import datasets, transforms

DEVICE = torch.device("cpu")
BATCHSIZE = 128
CLASSES = 10
DIR = os.getcwd()
EPOCHS = 100
LOG_INTERVAL = 10
STUDY_NAME = "pytorch-optimization"
FOLDER_NAME = randomname.get_name()


@click.command
@click.option("--epochs", type=int, default=EPOCHS, show_default=True)
@click.option("--batch-size", type=int, default=BATCHSIZE, show_default=True)
@click.option("--train-examples", type=int, default=BATCHSIZE * 30, show_default=True)
@click.option("--valid-examples", type=int, default=BATCHSIZE * 10, show_default=True)
@click.option("--trials", type=int, default=100, show_default=True)
@click.option("--timeout", type=int, default=600, show_default=True)
@click.option("--ci", is_flag=True, default=False)
def run_optuna_example(
    epochs: int,
    batch_size: int,
    train_examples: int,
    valid_examples: int,
    ci: bool,
    trials: int,
    timeout: int,
) -> None:
    if ci:
        batch_size = 1
        train_examples = 1
        valid_examples = 1
        epochs = 1
        trials = 1
        timeout = 30

    def train(optimizer, model, train_loader, batch_size=batch_size):
        model.train()
        for batch_idx, (data, target) in enumerate(train_loader):
            # Limiting training data for faster epochs.
            if batch_idx * batch_size >= train_examples:
                break

            data, target = data.view(data.size(0), -1).to(DEVICE), target.to(DEVICE)

            optimizer.zero_grad()
            output = model(data)
            loss = F.nll_loss(output, target)
            loss.backward()
            optimizer.step()

    def validate(model, valid_loader, batch_size=batch_size):
        # Validation of the model.
        model.eval()
        correct = 0
        with torch.no_grad():
            for batch_idx, (data, target) in enumerate(valid_loader):
                # Limiting validation data.
                if batch_idx * batch_size >= valid_examples:
                    break
                data, target = data.view(data.size(0), -1).to(DEVICE), target.to(DEVICE)
                output = model(data)
                # Get the index of the max log-probability.
                pred = output.argmax(dim=1, keepdim=True)
                correct += pred.eq(target.view_as(pred)).sum().item()

        accuracy = correct / min(len(valid_loader.dataset), valid_examples)

        return accuracy

    def define_model(trial):
        # We optimize the number of layers, hidden units and dropout ratio in each layer.
        n_layers = trial.suggest_int("n_layers", 1, 3)
        layers = []

        in_features = 28 * 28
        for i in range(n_layers):
            out_features = trial.suggest_int("n_units_l{}".format(i), 4, 128)
            layers.append(nn.Linear(in_features, out_features))
            layers.append(nn.ReLU())
            p = trial.suggest_float("dropout_l{}".format(i), 0.2, 0.5)
            layers.append(nn.Dropout(p))

            in_features = out_features
        layers.append(nn.Linear(in_features, CLASSES))
        layers.append(nn.LogSoftmax(dim=1))

        return nn.Sequential(*layers)

    # Get the data loaders of FashionMNIST dataset.
    train_loader = torch.utils.data.DataLoader(
        datasets.FashionMNIST(
            DIR, train=True, download=True, transform=transforms.ToTensor()
        ),
        batch_size=batch_size,
        shuffle=True,
    )
    valid_loader = torch.utils.data.DataLoader(
        datasets.FashionMNIST(DIR, train=False, transform=transforms.ToTensor()),
        batch_size=batch_size,
        shuffle=True,
    )

    def objective(trial):
        # Generate the model.
        model = define_model(trial).to(DEVICE)

        # Generate the optimizers.
        optimizer_name = trial.suggest_categorical(
            "optimizer", ["AdamW", "RMSprop", "SGD"]
        )
        lr = trial.suggest_float("lr", 1e-5, 1e-1, log=True)
        optimizer = getattr(optim, optimizer_name)(model.parameters(), lr=lr)

        # init tracking experiment.
        # hyper-parameters, trial id are stored.
        config = dict(trial.params)
        config["trial.number"] = trial.number
        from simvue import Run

        with Run() as run:
            run.init(
                folder="/optuna/tests/%s" % FOLDER_NAME,
                metadata=config,
                retention_period="1 hour" if ci else None,
            )

            # Training of the model.
            for epoch in range(epochs):
                train(optimizer, model, train_loader)
                val_accuracy = validate(model, valid_loader)
                trial.report(val_accuracy, epoch)

                # report validation accuracy to wandb
                run.log_metrics({"validation accuracy": val_accuracy}, step=epoch)

                # Handle pruning based on the intermediate value.
                if trial.should_prune():
                    run.update_metadata({"state": "pruned"})
                    run.close()
                    raise optuna.exceptions.TrialPruned()

            # report the final validation accuracy to simvue
            run.update_metadata({"final accuracy": val_accuracy, "state": "completed"})

        return val_accuracy

    study = optuna.create_study(
        direction="maximize",
        study_name=STUDY_NAME,
        pruner=optuna.pruners.MedianPruner(),
    )
    study.optimize(objective, n_trials=trials, timeout=timeout)


if __name__ in "__main__":
    run_optuna_example()
