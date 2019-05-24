""" Here we clean a running process from trailing lock files,
    crash files, etc.
"""

from argparse import Namespace
from datetime import datetime
import os.path
from termcolor import colored as clr
from .common.experiment_info import is_experiment
from .common.options_parser import OptionParser


def parse_options(strict: bool = True) -> Namespace:
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser(
        "liftoff-clean", ["config_path", "do", "verbose", "timestamp_fmt"]
    )

    return opt_parser.parse_args(strict=strict)


def clean_run(run_path, info, prefix, opts):
    """ Here we clean a run file.
    """
    lock_path = os.path.join(run_path, ".__lock")
    crash_path = os.path.join(run_path, ".__crash")
    start_path = os.path.join(run_path, ".__start")
    end_path = os.path.join(run_path, ".__end")

    lines = []
    lockers = info["lockers"]
    if os.path.exists(lock_path):
        info["nlocks"] += 1
        with open(lock_path, "r") as lock:
            session_id = lock.read().strip()
        lockers[session_id] = lockers.get(session_id, 0) + 1
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

    if opts.verbose and opts.verbose > 0:
        for line in lines:
            print(line, end="")
    if opts.do:
        with open(os.path.join(run_path, ".__journal"), "a") as j_hndlr:
            j_hndlr.writelines(lines)


def clean_experiment(opts):
    """ Clean a specific argument
    """
    info = {"nlocks": 0, "nstarted": 0, "ncrashed": 0, "lockers": dict({})}

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

    print(f"{info['nlocks']:d} .__lock files removed")
    print(f"{info['ncrashed']:d} .__crashed files removed")
    print(
        f"{info['nstarted']:d} .__start files removed "
        f"(not corresponding .__end or .__crash)"
    )

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
