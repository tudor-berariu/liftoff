""" Here we implement liftoff-status
"""

from argparse import Namespace
from collections import OrderedDict
import os.path
from typing import List
from tabulate import tabulate
from termcolor import colored as clr
from .common.experiment_info import get_experiment_paths
from .common.options_parser import OptionParser


def parse_options() -> Namespace:
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser(
        "liftoff-status", ["experiment", "all", "timestamp_fmt", "results_path"]
    )
    return opt_parser.parse_args()


def experiment_status(experiment_path):
    """ Gets full info about about an experiment.
    """
    counts = OrderedDict({
        ".__leaf": 0,
        ".__start": 0,
        ".__end": 0,
        ".__crash": 0,
        ".__lock": 0,
    })
    names = {
        ".__leaf": "Total",
        ".__start": "Started",
        ".__end": "Done",
        ".__crash": "Dead",
        ".__lock": "Locked",
    }
    with os.scandir(experiment_path) as fit:
        for entry in fit:
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            with os.scandir(entry.path) as fit2:
                for entry2 in fit2:
                    if entry2.name.startswith(".") or not entry2.is_dir():
                        continue
                    with os.scandir(entry2.path) as fit3:
                        for entry3 in fit3:
                            if entry3.name in counts:
                                counts[entry3.name] += 1
    info = OrderedDict({"Experiment": os.path.basename(experiment_path)})
    for key, value in counts.items():
        info[names[key]] = value
    progress = (info['Done'] + info['Dead']) * 100.0 / info['Total']
    info['Dead'] = clr(f"{info['Dead']:d}", color="red")
    info['Done'] = clr(f"{info['Done']:d}", color="green", attrs=["bold"])
    info["Progress"] = clr(f"{progress:.2f}%", attrs=['bold'])
    return info


def display_experiments(experiments_info: List[dict]):
    """ Here we nicely display the experiments.
    """
    print(tabulate(experiments_info, headers="keys"))


def status() -> None:
    """ Entry point for liftoff-status.
    """
    opts = parse_options()
    experiment_paths = get_experiment_paths(  # pylint: disable=bad-continuation
        opts.experiment,
        opts.results_path,
        opts.timestamp_fmt,
        latest=(not opts.all),
    )
    display_experiments(
        sorted(
            [experiment_status(p) for p in experiment_paths],
            key=lambda info: info["Experiment"],
        )
    )
