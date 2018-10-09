from argparse import Namespace
import os
import os.path
from time import time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms

from liftoff.config import read_config


class Net(nn.Module):
    def __init__(self, p_dropout: float = .5):
        super(Net, self).__init__()
        self.p_dropout = p_dropout
        self.conv1 = nn.Conv2d(1, 10, kernel_size=5)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
        self.conv2_drop = nn.Dropout2d(p=p_dropout)
        self.fc1 = nn.Linear(320, 50)
        self.fc2 = nn.Linear(50, 10)

    def forward(self, x):
        x = F.relu(F.max_pool2d(self.conv1(x), 2))
        x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))
        x = x.view(-1, 320)
        x = F.relu(self.fc1(x))
        x = F.dropout(x, p=self.p_dropout, training=self.training)
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)


def train(args, model, device, train_loader, optimizer, epoch):
    model.train()
    seen, last_seen = 0, 0
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = F.nll_loss(output, target)
        loss.backward()
        optimizer.step()
        seen += len(data)
        if seen - last_seen >= args.log_interval:
            last_seen = seen
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))


def test(args, model, device, test_loader):
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += F.nll_loss(output, target, reduction='sum').item()
            pred = output.max(1, keepdim=True)[1]
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)
    accuracy = 100. * correct / len(test_loader.dataset)
    print('\nTest set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        test_loss, correct, len(test_loader.dataset), accuracy))

    return accuracy


def run(args: Namespace) -> float:
    use_cuda = not args.no_cuda and torch.cuda.is_available()

    device = torch.device("cuda" if use_cuda else "cpu")

    kwargs = {'num_workers': 1, 'pin_memory': True} if use_cuda else {}
    train_loader = torch.utils.data.DataLoader(
        datasets.FashionMNIST('./.data', train=True, download=True,
                              transform=transforms.Compose([
                                  transforms.ToTensor(),
                                  transforms.Normalize((0.2860,), (0.3530,))
                              ])),
        batch_size=args.batch_size, shuffle=True, **kwargs)
    test_loader = torch.utils.data.DataLoader(
        datasets.FashionMNIST('./.data', train=False, transform=transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.2860,), (0.3530,))
        ])),
        batch_size=args.test_batch_size, shuffle=True, **kwargs)

    model = Net(p_dropout=args.dropout).to(device)
    optimizer = optim.SGD(model.parameters(),
                          lr=args.optimizer.lr,
                          momentum=args.optimizer.momentum,
                          nesterov=args.optimizer.nesterov)

    accuracies = []

    for epoch in range(1, args.training.epochs + 1):
        train(args, model, device, train_loader, optimizer, epoch)
        accuracies.append(test(args, model, device, test_loader))

    fitness = np.mean(accuracies)
    with open(os.path.join(args.out_dir, "fitness"), "w") as handler:
        handler.write(f"{fitness:.3f}")

    return fitness


def main() -> None:
    # Reading args
    args = read_config()  # type: Args

    if not hasattr(args, "out_dir"):
        if not os.path.isdir('./results'):
            os.mkdir('./results')
        out_dir = f'./results/{str(int(time())):s}_{args.experiment:s}'
        os.mkdir(out_dir)
        args.out_dir = out_dir
    elif not os.path.isdir(args.out_dir):
        raise Exception(f"Directory {args.out_dir} does not exist.")

    if not hasattr(args, "run_id"):
        args.run_id = 0

    run(args)


if __name__ == '__main__':
    main()
