import pickle
import math
import random
import os.path


def ndivs(val: int):
    return sum(1 for div in range(2, val) if val % div == 0)


def is_prime(val: int) -> bool:
    return ndivs(val) == 0


def nprime_divs(val: int):
    return sum(1 for p in range(2, val) if is_prime(p) and val % p == 0)


def is_square(val: int):
    sqr = int(math.sqrt(val))
    return val == sqr * sqr


def closest_square_distance(val: int):
    diff = 1
    while True:
        if is_square(val + diff):
            return diff
        if val > diff and is_square(val - diff):
            return diff
        diff += 1


def fitness(val: int):
    return random.gauss(val, 3.0)


def run(args):
    val = args.x
    summary = {
        "ndivs": ndivs(val),
        "nprime_divs": nprime_divs(val),
        "diff_to_sqr": closest_square_distance(val),
        "fitness": fitness(val)
    }

    with open(os.path.join(args.out_dir, 'summary.pkl'), 'wb') as handler:
        pickle.dump(summary, handler, pickle.HIGHEST_PROTOCOL)
    print("Done!")


def main() -> None:
    from liftoff.config import read_config
    args = read_config()
    run(args)


if __name__ == "__main__":
    main()
