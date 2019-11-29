""" Here we clean a running process from trailing lock files,
    crash files, etc.
"""

from argparse import Namespace
from datetime import datetime
from collections import defaultdict
import os.path
from termcolor import colored as clr
from .common.experiment_info import is_experiment
from .common.options_parser import OptionParser
from .common import LIFTOFF_FILES


def parse_options(strict: bool = True) -> Namespace:
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser(
        "liftoff-clean",
        ["config_path", "do", "clean_all", "verbose", "timestamp_fmt", "crashed_only"],
    )

    return opt_parser.parse_args(strict=strict)


def find_experiment_products(run_path):
    """ Find files that might be produced by an experiment, including but not
    limited to logs, tensorboard events, models, pickle binaries.
    """
    experiment_products = []
    with os.scandir(run_path) as fit:
        for entry in fit:
            if entry.name not in LIFTOFF_FILES and entry.is_file:
                experiment_products.append(entry)
    return experiment_products


def maybe_remove_all(opts, run_path, prefix, info, lines):
    """ Simulates, removes files provided by `find_experiment_products` and
    updates info.
    """
    product_paths = find_experiment_products(run_path)
    for entry in product_paths:
        info[entry.name] += 1
        if opts.do:
            os.remove(entry.path)
            lines.append(f"{prefix:s} Deleted {entry.name}\n")
    return info, lines


def clean_run(run_path, info, prefix, opts):
    """ Here we clean a run file.
    """
    lock_path = os.path.join(run_path, ".__lock")
    crash_path = os.path.join(run_path, ".__crash")
    start_path = os.path.join(run_path, ".__start")
    end_path = os.path.join(run_path, ".__end")
    seal_path = os.path.join(run_path, ".__seal")

    lines = []

    if opts.crashed_only and not os.path.exists(crash_path):
        return

    if os.path.exists(seal_path):
        info["nsealed"] += 1
        return

    if os.path.exists(lock_path):
        info["nlocks"] += 1
        if opts.do:
            os.remove(lock_path)
        lines.append(f"{prefix:s} Deleted {lock_path}\n")
    if os.path.exists(crash_path):
        info["ncrashed"] += 1
        if opts.do:
            os.remove(crash_path)
        lines.append(f"{prefix:s} Deleted {crash_path}\n")
    if os.path.exists(start_path) and not os.path.exists(end_path):
        info["nstarted"] += 1
        if opts.do:
            os.remove(start_path)
        lines.append(f"{prefix:s} Deleted {start_path}\n")
        # removes all the non-liftoff files in the experiment run
        if opts.clean_all:
            info, lines = maybe_remove_all(opts, run_path, prefix, info, lines)
    if opts.verbose and opts.verbose > 0:
        for line in lines:
            print(line, end="")
    if opts.do:
        with open(os.path.join(run_path, ".__journal"), "a") as j_hndlr:
            j_hndlr.writelines(lines)


def clean_experiment(opts):
    """ Clean a specific argument
    """
    info = defaultdict(int)

    experiment_path = opts.experiment_path

    timestamp = f"{datetime.now():{opts.timestamp_fmt:s}}"
    prefix = f"[{timestamp:s}][{opts.session_id}]"
    with os.scandir(experiment_path) as fit:
        for entry in fit:
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            with os.scandir(entry.path) as fit2:
                for entry2 in fit2:
                    if entry2.name.startswith(".") or not entry2.is_dir():
                        continue
                    clean_run(entry2.path, info, prefix, opts)

    print(f"{info['nsealed']:d} runs are sealed.")
    print(f"{info['nlocks']:d} .__lock files removed")
    print(f"{info['ncrashed']:d} .__crashed files removed")
    print(
        f"{info['nstarted']:d} .__start files removed "
        f"(not corresponding .__end or .__crash)"
    )
    if opts.clean_all:
        print("\nFiles produced by the experiment run: ")
        for key, val in info.items():
            if key not in ["nlocks", "ncrashed", "nstarted"]:
                print(f"{val:d} {key} files removed.")

    if not opts.do:
        print(
            "\nThis was just a simultation. Rerun with",
            clr("--do", attrs=["bold"]),
            "to clean the experiment for real.",
        )


def clean():
    """ Main function for liftoff-clean.
    """
    opts = parse_options()
    if not is_experiment(opts.config_path):
        raise RuntimeError(f"{opts.config_path:s} is not a liftoff experiment")
    opts.experiment_path = opts.config_path
    clean_experiment(opts)
