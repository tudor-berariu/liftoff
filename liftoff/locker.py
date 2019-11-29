""" Here we lock some experiments.
    Not a very useful feature in general.
"""

from argparse import Namespace
from datetime import datetime
from collections import defaultdict
import os
from termcolor import colored as clr
from .common.experiment_info import is_experiment
from .common.options_parser import OptionParser
from .liftoff import lock_file


def parse_options(strict: bool = True) -> Namespace:
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser(
        "liftoff-lock", ["config_path", "do", "runs", "verbose", "timestamp_fmt"]
    )

    return opt_parser.parse_args(strict=strict)


def lock_run(run_path, info, prefix, opts):
    """ Lock a run if possible.
    """
    lines = []
    existing_files = os.listdir(run_path)

    if "cfg.yaml" not in existing_files or ".__leaf" not in existing_files:
        info["nstrange"] += 1
        return

    for must_not_be in [".__start", ".__lock", ".__end", ".__crash"]:
        if must_not_be in existing_files:
            info["nstarted"] += 1
            return

    info["nlocks"] += 1
    if opts.do:
        if lock_file(os.path.join(run_path, ".__lock"), opts.session_id):
            with open(os.path.join(run_path, ".__seal"), "w") as hndlr:
                hndlr.write(f"{opts.session_id}\n")
            lines.append(f"{prefix:s} Locked and sealed.\n")
        else:
            info["nlocks"] -= 1
            info["nraced"] += 1

    if opts.verbose and opts.verbose > 0:
        for line in lines:
            print(line, end="")
    if opts.do:
        with open(os.path.join(run_path, ".__journal"), "a") as j_hndlr:
            j_hndlr.writelines(lines)


def lock_experiment(opts):
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
                    try:
                        run_id = int(entry2.name)
                        if run_id in opts.runs:
                            lock_run(entry2.path, info, prefix, opts)
                    except ValueError:
                        pass

    print(f"{info['nlocks']:d} .__lock files added")
    print(f"{info['nraced']:d} times we just lost the .__lock to some other process")

    if not opts.do:
        print(
            "\nThis was just a simultation. Rerun with",
            clr("--do", attrs=["bold"]),
            "to clean the experiment for real.",
        )


def lock():
    """ Main function for liftoff-clean.
    """
    opts = parse_options()
    if not is_experiment(opts.config_path):
        raise RuntimeError(f"{opts.config_path:s} is not a liftoff experiment")
    opts.experiment_path = opts.config_path
    lock_experiment(opts)
