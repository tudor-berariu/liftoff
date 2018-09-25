from argparse import ArgumentParser, Namespace
import os
import heapq
import yaml
from termcolor import colored as clr
import tabulate


def parse_args() -> Namespace:
    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "-e", "--experiment", type=str, dest="experiment",
        help="Get by name.")
    arg_parser.add_argument(
        "-t", "--timestamp", type=str, dest="timestamp",
        help="Get by timestamp.")
    arg_parser.add_argument(
        "-n", "--top", type=int, dest="top_n", default=3,
        help="Show top n individuals")
    arg_parser.add_argument(
        "-d", "--results-dir", dest="results_dir", default="results",
        help="Results directory (default: ./results)")

    return arg_parser.parse_args()


def elite() -> None:
    args = parse_args()

    candidate_exps = []
    for dirname in os.listdir(args.results_dir):
        if os.path.isdir(os.path.join(args.results_dir, dirname)):
            candidate_exps.append(dirname)

    if hasattr(args, "timestamp") and args.timestamp:
        candidate_exps = [d for d in candidate_exps if d.startswith(args.timestamp)]

    if hasattr(args, "experiment") and args.experiment:
        candidate_exps = [d for d in candidate_exps if d.endswith("_" + args.experiment)]

    assert candidate_exps

    last_time = str(max([int(f.split("_")[0]) for f in candidate_exps]))
    exp_name = [d for d in candidate_exps if d.startswith(last_time)][0]
    exp_path = os.path.join(args.results_dir, exp_name)

    top_n = []

    for rel_path, _, files in os.walk(exp_path):
        if ".__leaf" in files and "fitness" in files:
            with open(os.path.join(rel_path, "fitness")) as handler:
                fitness = float(handler.readline().strip())

            if len(top_n) < args.top_n or fitness > top_n[0][0]:
                ph_path = os.path.join(rel_path, "phenotype.yaml")
                heapq.heappush(top_n, (fitness, ph_path))
                if len(top_n) > args.top_n:
                    heapq.heappop(top_n)

    lst = []
    while top_n:
        lst.append(heapq.heappop(top_n))
    lst.reverse()

    for (fitness, path) in lst:
        with open(path) as handler:
            data = yaml.load(handler, Loader=yaml.SafeLoader)

        queue = [("", data)]
        pairs = []

        while queue:
            prev, x = queue.pop(0)
            if isinstance(x, dict):
                for key, value in x.items():
                    queue.append((((prev + ".") if prev else "") + key, value))
            else:
                pairs.append((prev, x))
        pairs.sort(key=lambda x: x[0])

        print(f"{clr('***', 'red'):s} Fitness: {clr(f'{fitness:.2f}', 'yellow'):s} {clr('***', 'red'):s}")
        print(tabulate.tabulate(pairs))

        print("\n")
