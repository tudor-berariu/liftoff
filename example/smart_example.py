from time import time, sleep
import os
from argparse import Namespace
from numpy.random import randint

from liftoff.config import read_config, config_to_string


def run(args: Namespace) -> None:
    print(f"[{args.run_id:d}] Starting.", flush=True)
    print(f"[{args.run_id:d}] Got this:", config_to_string(args), flush=True)
    print(f"Computing {args.x:d} + {args.yz.y:d} + {args.yz.z:d} = ",
          end="", flush=True)
    for i in range(4):
        sleep(randint(1, 4))
        open(os.path.join(args.out_dir, f"step__{i:d}__results"), "w").close()
    print(f"... ", end="", flush=True)
    if randint(1, 8) % 7 == 0:
        _ = [][0]  # Error
    sleep(randint(1, 5))
    print(args.x + args.yz.y + args.yz.z, flush=True)
    print(f"[{args.run_id:d}] Done.", flush=True)
    open(os.path.join(args.out_dir, f"results"), "w").close()


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
