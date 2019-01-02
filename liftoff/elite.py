from collections import OrderedDict
from typing import List
import os
from argparse import Namespace, ArgumentParser
from itertools import chain
import pickle
import numpy as np
import yaml
from tabulate import tabulate
from termcolor import colored as clr

from .common.argparsers import add_experiment_lookup_args
from .common.lookup import get_latest_experiment
from .version import welcome


def add_reporting_args(arg_parser: ArgumentParser) -> None:
    arg_parser.add_argument(
        "-n",
        type=int,
        dest="top_n",
        default=0,
        help="Show top n individuals (averages). Default: 0 (all)",
    )
    arg_parser.add_argument(
        "-s",
        "--sort",
        type=str,
        nargs="*",
        dest="sort_fields",
        default=[],
        help="Sort by these fields.",
    )
    arg_parser.add_argument(
        "-i",
        "--individual",
        dest="individual",
        default=False,
        action="store_true",
        help="Do not average over runs.",
    )
    arg_parser.add_argument(
        "--vert",
        dest="vertical",
        default=False,
        action="store_true",
        help="Show on vertical",
    )
    arg_parser.add_argument(
        "--title",
        dest="just_title",
        default=False,
        action="store_true",
        help="Show just the title for each run.",
    )
    arg_parser.add_argument(
        "-a",
        "--all",
        dest="get_all",
        default=False,
        action="store_true",
        help="Display experiments with no summary also",
    )


def parse_args() -> Namespace:
    arg_parser = ArgumentParser()
    add_experiment_lookup_args(arg_parser)
    add_reporting_args(arg_parser)
    return arg_parser.parse_args()


def get_run_summary(run_path: str) -> dict:
    summary_path = os.path.join(run_path, "summary.pkl")
    if os.path.isfile(summary_path):
        with open(summary_path, "rb") as handler:
            summary = pickle.load(handler)
        return summary

    fitness_path = os.path.join(run_path, "fitness")
    if os.path.isfile(fitness_path):
        with open(fitness_path, "r") as handler:
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


def collect_runs(  # pylint: disable=C0330
    exp_path: str,
    individual: bool = False,
    just_title: bool = False,
    get_all: bool = False,
):
    all_runs = dict({})  # type: Dict[str, Any]
    for run_path, _, files in os.walk(exp_path):
        if ".__leaf" in files:
            summary = get_run_summary(run_path)
            if (not summary) and (not get_all):
                continue
            details = get_run_parameters(run_path, just_title=just_title)

            if individual:
                all_runs[run_path] = (summary, details)
            else:
                config_path, maybe_run_id = os.path.split(run_path)
                try:
                    run_id = int(maybe_run_id)
                    if run_id != details["run_id"]:
                        raise RuntimeError(
                            "run_id does not match folder: " + run_path
                        )
                    key = config_path
                except ValueError:  # There were no extra runs
                    key = run_path
                if "run_id" in details:
                    del details["run_id"]

                all_runs.setdefault(key, []).append((summary, details))
    return all_runs


def aggregate(all_runs, sort_criteria: OrderedDict):
    new_runs = {}
    for run_path, runs in all_runs.items():
        values = {}  # type: Dict[str, List[float]]
        for (summary, _) in runs:
            for key, value in summary.items():
                values.setdefault(key, []).append(value)
        aggrs = {}
        for key, vals in values.items():
            agg_op, _order = sort_criteria.get(key, ("avg", None))
            if agg_op == "avg":
                aggrs[key] = np.mean(vals), np.std(vals)
            elif agg_op == "max":
                aggrs[key] = np.max(vals), None
            elif agg_op == "min":
                aggrs[key] = np.min(vals), None
            else:
                raise RuntimeError

        new_runs[run_path] = aggrs, runs[0][1]  # (summary, details)
    return new_runs


def get_top(all_runs: dict, top_n: int, sort_criteria: OrderedDict):
    def sort_key(run):
        key = []
        for name, (_, order) in sort_criteria.items():
            val = run[1][0][name]
            val = val[0] if isinstance(val, tuple) else val
            key.append(val * (-1 if order == "desc" else 1))
        return tuple(key)

    srt = sorted(all_runs.items(), key=sort_key)
    if top_n > 0:
        srt = srt[:top_n]
    return srt


def process_sort_fields(  #  pylint: disable=C0330
    sort_fields: List[str], default_op: str = "avg", default_order: str = "desc"
) -> OrderedDict:
    ops = ["max", "avg", "min"]
    orders = ["asc", "desc"]

    sort_order = OrderedDict({})  # type: OrderedDict[str, Tuple[str, str]]
    for field in sort_fields:
        name, *details = field.split(":")
        agg_op, order = None, None
        for detail in details:
            if detail in ops:
                agg_op = detail
            elif detail in orders:
                order = detail
        agg_op = default_op if agg_op is None else agg_op
        order = default_order if order is None else order
        sort_order[name] = agg_op, order
    return sort_order


def elite() -> None:
    welcome()
    args = parse_args()
    exp_name, exp_path = get_latest_experiment(**args.__dict__)

    print("Experiment", clr(exp_name, "yellow", attrs=["bold"]), "\n")

    all_runs = collect_runs(
        exp_path,
        args.individual,
        just_title=args.just_title,
        get_all=args.get_all,
    )
    sort_criteria = process_sort_fields(args.sort_fields)
    if not args.individual:
        all_runs = aggregate(all_runs, sort_criteria)
    runs = get_top(all_runs, args.top_n, sort_criteria)

    if not args.vertical:
        summary_keys = list(set(chain(*(r[1][0].keys() for r in runs))))
        details_keys = list(set(chain(*(r[1][1].keys() for r in runs))))
        summary_keys = [k for k in summary_keys if k not in sort_criteria]

        table = []
        for _, (summary, details) in runs:
            vals = []
            for key in details_keys:
                vals.append(details.get(key, None))
            for key in sort_criteria.keys():
                val = summary.get(key, None)
                if isinstance(val, tuple):
                    vals.extend(val)
                else:
                    vals.append(val)
            for key in summary_keys:
                val = summary.get(key, None)
                if isinstance(val, tuple):
                    vals.extend(val)
                else:
                    vals.append(val)
            table.append(tuple(vals))
        header = []
        header.extend(details_keys)
        if args.individual:
            header.extend(list(sort_criteria.keys()))
            header.extend(summary_keys)
        else:
            for name in sort_criteria.keys():
                header.extend([name, ""])
            for name in summary_keys:
                header.extend([name, ""])
        print(tabulate(table, headers=header))

    else:
        for path, (summary, details) in runs:
            info = [["Path", path]]
            info.extend(list(it) for it in details.items())
            for key, val in summary.items():
                if key in sort_criteria:
                    key = clr(key, "yellow")
                if isinstance(val, tuple):
                    mean, std = val
                    info.append([key, mean, std])
                else:
                    info.append([key, val])
            print(tabulate(info))
