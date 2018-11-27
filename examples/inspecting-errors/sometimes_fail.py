from argparse import Namespace
import random


def run(_args: Namespace):
    my_op = random.randint(0, 4)
    if my_op == 0:
        return [1, 2, 3] + 4
    elif my_op == 1:
        return [1, 2, 3][4]
    elif my_op == 2:
        # pylint: disable=E1126
        return [1, 2, 3]["4"]


if __name__ == "__main__":
    run(Namespace())
