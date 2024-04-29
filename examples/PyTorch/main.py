# Taken from https://github.com/pytorch/examples/blob/main/mnist/main.py
from __future__ import print_function

import click

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
from torchvision import datasets, transforms

from simvue import Run


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.dropout1 = nn.Dropout(0.25)
        self.dropout2 = nn.Dropout(0.5)
        self.fc1 = nn.Linear(9216, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = F.relu(x)
        x = self.conv2(x)
        x = F.relu(x)
        x = F.max_pool2d(x, 2)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)
        x = self.fc1(x)
        x = F.relu(x)
        x = self.dropout2(x)
        x = self.fc2(x)
        output = F.log_softmax(x, dim=1)
        return output


def train(
    dry_run: bool,
    log_interval: int,
    model,
    device,
    train_loader,
    optimizer,
    epoch,
    run: Run,
) -> None:
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()
        if batch_idx % log_interval == 0:
            print(
                "Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}".format(
                    epoch,
                    batch_idx * len(data),
                    len(train_loader.dataset),
                    100.0 * batch_idx / len(train_loader),
                    loss.item(),
                )
            )
            run.log_metrics(
                {"train.loss.%d" % epoch: float(loss.item())}, step=batch_idx
            )
            if dry_run:
                break


def test(model, device, test_loader, epoch, run):
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += F.nll_loss(
                output, target, reduction="sum"
            ).item()  # sum up batch loss
            pred = output.argmax(
                dim=1, keepdim=True
            )  # get the index of the max log-probability
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)
    test_accuracy = 100.0 * correct / len(test_loader.dataset)

    print(
        "\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n".format(
            test_loss, correct, len(test_loader.dataset), test_accuracy
        )
    )
    run.log_metrics(
        {"test.loss": test_loss, "test.accuracy": test_accuracy}, step=epoch
    )


@click.command
@click.option(
    "--batch-size",
    type=int,
    default=64,
    help="input batch size for training",
    show_default=True,
)
@click.option(
    "--test-batch-size",
    type=int,
    default=1000,
    help="input batch size for testing",
    show_default=True,
)
@click.option(
    "--epochs",
    type=int,
    default=14,
    help="number of epochs to train",
    show_default=True,
)
@click.option("--lr", type=float, default=1.0, help="learning rate", show_default=True)
@click.option(
    "--gamma",
    type=float,
    default=0.7,
    help="learning rate step gamma",
    show_default=True,
)
@click.option(
    "--no-cuda",
    is_flag=True,
    default=False,
    help="disables CUDA training",
    show_default=True,
)
@click.option(
    "--no-mps",
    is_flag=True,
    default=False,
    help="disables macOS GPU training",
    show_default=True,
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="quickly check a single pass",
    show_default=True,
)
@click.option("--seed", type=int, default=1, help="random seed", show_default=True)
@click.option(
    "--log-interval",
    type=int,
    default=10,
    help="how many batches to wait before logging training status",
    show_default=True,
)
@click.option(
    "--save-model",
    is_flag=True,
    default=False,
    help="save the current Model",
    show_default=True,
)
@click.option("--ci", is_flag=True, default=False)
def simvue_pytorch_example(
    batch_size: int,
    test_batch_size: int,
    epochs: int,
    lr: float,
    gamma: float,
    no_cuda: bool,
    no_mps: bool,
    dry_run: bool,
    seed: int,
    log_interval: int,
    save_model: bool,
    ci: bool,
) -> None:
    use_cuda = not no_cuda and torch.cuda.is_available() and not ci
    use_mps = not no_mps and torch.backends.mps.is_available() and not ci

    torch.manual_seed(seed)

    if use_cuda:
        device = torch.device("cuda")
    elif use_mps:
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    if ci:
        dry_run = True
        batch_size = 1
        test_batch_size = 1
        epochs = 1
        save_model = False

    train_kwargs = {"batch_size": batch_size}
    test_kwargs = {"batch_size": test_batch_size}
    if use_cuda:
        cuda_kwargs = {"num_workers": 1, "pin_memory": True, "shuffle": True}
        train_kwupdate(cuda_kwargs)
        test_kwupdate(cuda_kwargs)

    transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))]
    )
    dataset1 = datasets.MNIST("../data", train=True, download=True, transform=transform)
    dataset2 = datasets.MNIST("../data", train=False, transform=transform)
    train_loader = torch.utils.data.DataLoader(dataset1, **train_kwargs)
    test_loader = torch.utils.data.DataLoader(dataset2, **test_kwargs)

    model = Net().to(device)
    optimizer = optim.Adadelta(model.parameters(), lr=lr)

    scheduler = StepLR(optimizer, step_size=1, gamma=gamma)

    with Run() as run:
        run.init(
            tags=["PyTorch"],
            folder="/simvue_client_demos",
            ttl=60 * 60 if ci else -1,
        )

        for epoch in range(1, epochs + 1):
            train(
                dry_run,
                log_interval,
                model,
                device,
                train_loader,
                optimizer,
                epoch,
                run,
            )
            test(model, device, test_loader, epoch, run)
            scheduler.step()

        if save_model:
            run.save(model.state_dict(), "output", name="mnist_cnn.pt")


if __name__ == "__main__":
    simvue_pytorch_example()
