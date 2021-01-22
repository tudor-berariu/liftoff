""" Here we implement liftoff-status
"""

from argparse import Namespace
from collections import OrderedDict
import datetime
import os.path
import sys
import time
from typing import List
from tabulate import tabulate
from termcolor import colored as clr
import numpy as np
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
    ntotal, nstarted, nended, ncrashed, nlocked, nlost = 0, 0, 0, 0, 0, 0
    durations = []
    live_durations = []

    time0 = time.time()
    time_now = time.time()  # Time now

    with os.scandir(experiment_path) as fit:
        for entry in fit:
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            with os.scandir(entry.path) as fit2:
                for entry2 in fit2:
                    if entry2.name.startswith(".") or not entry2.is_dir():
                        continue
                    leaf_path = os.path.join(entry2.path, ".__leaf")
                    if not os.path.isfile(leaf_path):
                        continue

                    ntotal += 1

                    start_path = os.path.join(entry2.path, ".__start")
                    lock_path = os.path.join(entry2.path, ".__lock")
                    if os.path.isfile(start_path):
                        nstarted += 1
                        with open(start_path) as start_file:
                            try:
                                start_time = int(start_file.readline().strip())
                                time0 = min(start_time, time0)
                            except ValueError as _ex:
                                sys.stderr.write(
                                    f"Can't read timestamp in {start_path}.\n"
                                )

                            end_path = os.path.join(entry2.path, ".__end")
                            crash_path = os.path.join(entry2.path, ".__crash")

                            if os.path.isfile(end_path):
                                with open(end_path) as end_file:
                                    try:
                                        end_time = int(end_file.readline().strip())
                                        durations.append(end_time - start_time)
                                    except ValueError as _ex:
                                        sys.stderr.write(
                                            f"Can't read timestamp in {end_path}.\n"
                                        )
                                nended += 1
                            elif os.path.isfile(crash_path):
                                with open(crash_path) as end_file:
                                    try:
                                        end_time = int(end_file.readline().strip())
                                        durations.append(end_time - start_time)
                                    except ValueError as _ex:
                                        sys.stderr.write(
                                            f"Can't read timestamp in {crash_path}.\n"
                                        )
                                ncrashed += 1
                            elif os.path.isfile(lock_path):
                                nlocked += 1
                                live_durations.append(time_now - start_time)
                            else:
                                nlost += 1
                    elif os.path.isfile(lock_path):
                        nlocked += 1

    durations, live_durations = np.array(durations), np.array(live_durations)

    if durations.size > 0:
        avg_time = np.mean(durations)  # Average time based on finished runs
        # Here we limit the locked processes to maximum two standard deviations above
        # the mean known duration.
        # Without this a process locked and abandoned might add too much progress.
        # It's better to underestimate progress than to overestimate it. :)
        mean, std = np.mean(durations), np.std(durations)
        live_durations = live_durations.clip(0, mean + 2 * std)
    elif live_durations.size > 0:
        avg_time = np.mean(live_durations) * 2
    else:
        avg_time = 0

    if avg_time > 0:
        live_time_left = np.sum(avg_time - live_durations)
        nleft = ntotal - nended - ncrashed - len(live_durations)
        is_over = (nleft > 0) or (live_durations.size > 0)

        time_left = max(avg_time * nleft + live_time_left, 0 if is_over else 1)

        elapsed_time = np.sum(durations) + np.sum(live_durations)
        speedup = elapsed_time / (time_now - time0)

        left_wall_time = datetime.timedelta(seconds=int(time_left / speedup))

        progress = min(100.0 * elapsed_time / (elapsed_time + time_left), 100.0)

    else:
        progress = 0
        left_wall_time = datetime.timedelta(days=100)

    info = OrderedDict({})
    info["Experiment"] = os.path.basename(experiment_path)
    info["Total"] = f"{ntotal:d}"
    info["Locked"] = f"{nlocked:d}"
    info["Done"] = clr(f"{nended:d}", "green")
    info["Dead"] = clr(f"{ncrashed:d}", "red")
    if nlost > 0:
        info["Lost"] = clr(f"{nlost:d}", "white", "on_magenta", attrs=["bold"])
    info["Progress"] = clr(f"{progress:.3f}%", attrs=["bold"])
    info["ETL"] = str(left_wall_time)

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
        opts.experiment, opts.results_path, opts.timestamp_fmt, latest=(not opts.all),
    )
    display_experiments(
        sorted(
            [experiment_status(p) for p in experiment_paths],
            key=lambda info: info["Experiment"],
        )
    )
