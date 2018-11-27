from typing import List
import os
from argparse import Namespace, ArgumentParser
from itertools import chain
import pickle
import numpy as np
import yaml
from tabulate import tabulate
from termcolor import colored as clr

from liftoff.common import get_latest_experiment
from liftoff.common import add_experiment_lookup_args
from liftoff.version import welcome


# TODO: vertical mode
# TODO: add std.
# TODO: add max / min (not only avg)
# TODO: add sorting order


def add_reporting_args(arg_parser: ArgumentParser) -> None:
    arg_parser.add_argument(
        "-n",
        type=int,
        dest="top_n",
        default=0,
        help="Show top n individuals (averages). Default: 0 (all)")
    arg_parser.add_argument(
        "-s", "--sort",
        type=str,
        nargs="*",
        dest="sort_fields",
        default=[],
        help="Sort by these fields.")
    arg_parser.add_argument(
        "-i", "--individual",
        dest="individual",
        default=False,
        action="store_true",
        help="Do not average over runs.")
    arg_parser.add_argument(
        "--vert",
        dest="vertical",
        default=False,
        action="store_true",
        help="Show on vertical")
    arg_parser.add_argument(
        "--title",
        dest="just_title",
        default=False,
        action="store_true",
        help="Show just the title for each run."
    )


def parse_args() -> Namespace:
    arg_parser = ArgumentParser()
    add_experiment_lookup_args(arg_parser)
    add_reporting_args(arg_parser)
    return arg_parser.parse_args()


def get_run_summary(run_path: str) -> dict:
    summary_path = os.path.join(run_path, "summary.pkl")
    if os.path.isfile(summary_path):
        with open(summary_path, 'rb') as handler:
            summary = pickle.load(handler)
        return summary

    fitness_path = os.path.join(run_path, "fitness")
    if os.path.isfile(fitness_path):
        with open(fitness_path) as handler:
            fitness = float(handler.readline().strip())
        return {"fitness": fitness}

    return dict({})


def get_run_parameters(run_path: str, just_title: bool = False) -> dict:
    cfg_path = os.path.join(run_path, "cfg.yaml")

    if os.path.isfile(cfg_path):
        with open(cfg_path) as handler:
            all_data = yaml.load(handler, Loader=yaml.SafeLoader)
        if (not just_title) and "_experiment_parameters" in all_data:
            data = all_data["_experiment_parameters"]
            data["run_id"] = all_data.get("run_id", 0)
        else:
            data = {}
            data["run_id"] = all_data.get("run_id", 0)
            data["title"] = all_data["title"]
        return data
    return dict({})


def collect_runs(exp_path: str, individual: bool = False,
                 just_title: bool = False):
    all_runs = dict({})
    for run_path, _, files in os.walk(exp_path):
        if ".__leaf" in files:
            summary = get_run_summary(run_path)
            details = get_run_parameters(run_path, just_title=just_title)

            if individual:
                all_runs[run_path] = (summary, details)
            else:
                config_path, maybe_run_id = os.path.split(run_path)
                try:
                    run_id = int(maybe_run_id)
                    if run_id != details["run_id"]:
                        raise RuntimeError("run_id does not match folder: " +
                                           run_path)
                    key = config_path
                except ValueError:  # There were no extra runs
                    key = run_path
                if "run_id" in details:
                    del details["run_id"]

                all_runs.setdefault(key, []).append((summary, details))

    if not individual:
        new_runs = {}
        for run_path, runs in all_runs.items():
            avgs = {}
            for (summary, details) in runs:
                for key, value in summary.items():
                    avgs.setdefault(key, []).append(value)
            avgs = {key: np.mean(vals) for (key, vals) in avgs.items()}
            new_runs[run_path] = avgs, runs[0][1]
        all_runs = new_runs

    return all_runs


def get_top(all_runs: dict, top_n: int, sort_fields: List[str]):
    def sort_key(run):
        return tuple(run[1][0][k] for k in sort_fields)
    srt = sorted(all_runs.items(), key=sort_key, reverse=True)
    if top_n > 0:
        srt = srt[:top_n]
    return srt


def elite() -> None:
    welcome()
    args = parse_args()
    exp_name, exp_path = get_latest_experiment(**args.__dict__)

    print("Experiment", clr(exp_name, "yellow", attrs=['bold']), "\n")

    all_runs = collect_runs(exp_path, args.individual,
                            just_title=args.just_title)
    runs = get_top(all_runs, args.top_n, args.sort_fields)

    if not args.vertical:
        summary_keys = list(set(chain(*(r[1][0].keys() for r in runs))))
        details_keys = list(set(chain(*(r[1][1].keys() for r in runs))))
        summary_keys = [k for k in summary_keys if k not in args.sort_fields]

        table = []
        for _, (summary, details) in runs:
            vals = []
            for key in details_keys:
                vals.append(details.get(key, None))
            if args.sort_fields:
                for key in args.sort_fields:
                    vals.append(summary.get(key, None))
            for key in summary_keys:
                vals.append(summary.get(key, None))
            table.append(tuple(vals))
        header = []
        header.extend(details_keys)
        if args.sort_fields:
            header.extend(args.sort_fields)
        header.extend(summary_keys)

        print(tabulate(table, headers=header))

    else:
        raise NotImplementedError
