from argparse import Namespace
import os.path
import numpy as np

from liftoff.config import read_config


PROPERTIES = {
    # name: (profit, weight)
    "platinum": (20, 10),
    "gold": (17, 10),
    "silver": (8, 5),
    "bronze": (5, 4),
    "coal": (3, 3),
    "wood": (1, 2)
}

CATEGORICAL = {"none": 0, "some": 5, "much": 25}

MAX_WEIGHT = 1500


def run(args: Namespace) -> float:
    total_weight, total_profit = 0, 0
    quantities = {}
    for rock in ["gold", "silver", "bronze"]:
        quantities[rock] = getattr(args.rocks, rock)
    for other in ["wood", "coal"]:
        quantities[other] = CATEGORICAL[getattr(args, other)]

    print(quantities)

    for material, quantity in quantities.items():
        profit, weight = PROPERTIES[material]
        total_weight += weight * quantity
        total_profit += profit * quantity

    profit += np.random.sample()

    fitness = max(total_profit + min(0, MAX_WEIGHT - total_weight) * total_profit, 0)
    print(args.out_dir)
    with open(os.path.join(args.out_dir, "fitness"), 'w') as filehandler:
        filehandler.write(f"{fitness:.2f}\n")
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


if __name__ == "__main__":
    main()
