from time import time, sleep
import os
from argparse import Namespace
from numpy.random import randint

from liftoff.config import read_config, config_to_string


def run(args: Namespace):
    print(f"[{args.run_id:d}] Starting.", flush=True)
    print(f"[{args.run_id:d}] Got this:", config_to_string(args), flush=True)
    print(f"Computing {int(args.x):d} + {int(args.y):d} = ",
          end="", flush=True)
    sleep(randint(2, 10))
    print(args.x + args.y, flush=True)
    print(f"[{args.run_id:d}] Done.", flush=True)


def main():
    # Reading args
    args = read_config()  # type: Args

    if not hasattr(args, "out_dir"):
        if not os.path.isdir('./results'):
            os.mkdir('./results')
        out_dir = f'./results/{str(int(time())):s}_{args.experiment:s}'
        os.mkdir(out_dir)
        args.out_dir = out_dir
    else:
        assert os.path.isdir(args.out_dir), "Given directory does not exist"

    if not hasattr(args, "run_id"):
        args.run_id = 0

    run(args)


if __name__ == "__main__":
    main()
