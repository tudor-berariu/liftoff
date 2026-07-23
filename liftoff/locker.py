"""Here we lock some experiments.
Not a very useful feature in general.
"""

import os
from argparse import Namespace
from datetime import datetime

from termcolor import colored as clr

from .common.experiment_info import experiment_matches, is_experiment
from .common.options_parser import OptionParser

_RUN_MARKERS = frozenset({".__lock", ".__start", ".__end", ".__crash"})


def parse_options(strict: bool = True) -> Namespace:
    """Parse command line arguments and liftoff configuration."""

    opt_parser = OptionParser(
        "liftoff-lock",
        ["config_path", "runs", "filters", "do", "verbose", "timestamp_fmt"],
    )

    return opt_parser.parse_args(strict=strict)


def unlock_run(run_path, prefix, opts) -> str:
    """Unlock a run if possible.

    Returns one of: "unlocked", "strange", "no_seal".
    """
    lines: list[str] = []
    existing_files = os.listdir(run_path)

    if "cfg.yaml" not in existing_files or ".__leaf" not in existing_files:
        return "strange"

    if ".__seal" not in existing_files:
        return "no_seal"

    if ".__lock" in existing_files and opts.do:
        os.remove(os.path.join(run_path, ".__lock"))

    if opts.do:
        os.remove(os.path.join(run_path, ".__seal"))

    lines.append(f"{prefix:s} Unlocked and unsealed {run_path}.\n")

    if opts.do:
        with open(os.path.join(run_path, ".__journal"), "a") as j_hndlr:
            j_hndlr.writelines(lines)

    return "unlocked"


def lock_run(run_path, prefix, opts) -> str:
    """Lock a run if possible.

    Returns one of: "locked", "already_started", "strange", "raced".
    """
    from .liftoff import lock_file

    existing_files = os.listdir(run_path)

    if "cfg.yaml" not in existing_files or ".__leaf" not in existing_files:
        return "strange"

    if any(marker in existing_files for marker in _RUN_MARKERS):
        return "already_started"

    journal_line = f"{prefix:s} Locked and sealed {run_path}.\n"
    if opts.do:
        if not lock_file(os.path.join(run_path, ".__lock"), opts.session_id):
            return "raced"
        with open(os.path.join(run_path, ".__seal"), "w") as hndlr:
            hndlr.write(f"{opts.session_id}\n")
        with open(os.path.join(run_path, ".__journal"), "a") as j_hndlr:
            j_hndlr.write(journal_line)
    if opts.verbose and opts.verbose > 0:
        print(journal_line, end="")
    return "locked"


def change_experiment_lock_status(opts, unlock=False):
    """Lock or Unlock experiments given the RUNS and FILTERS provided in opts.
    FILTERS allows for selecting experiments based on their configuration.
    For example experiments containing the configuration `a.b=c` can be targeted.
    """
    experiment_path = opts.experiment_path
    filters = opts.filters

    timestamp = f"{datetime.now():{opts.timestamp_fmt:s}}"
    prefix = f"[{timestamp:s}][{opts.session_id}]"
    counts: dict[str, int] = {}
    with os.scandir(experiment_path) as fit:
        for entry in fit:
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            with os.scandir(entry.path) as fit2:
                for entry2 in fit2:
                    if entry2.name.startswith(".") or not entry2.is_dir():
                        continue
                    try:
                        # if `filters` is not provided lock/unlock experiments
                        # based on the mandatory `runs` argument. Else, check if
                        # experiment matches any of the filters provided.
                        target_experiment = True
                        if filters is not None:
                            run_path = f"{experiment_path}/{entry.name}/{entry2.name}"
                            target_experiment = experiment_matches(run_path, filters)

                        run_id = int(entry2.name)
                        if target_experiment and run_id in opts.runs:
                            status = (
                                unlock_run(entry2.path, prefix, opts)
                                if unlock
                                else lock_run(entry2.path, prefix, opts)
                            )
                            counts[status] = counts.get(status, 0) + 1
                    except ValueError:
                        pass

    nlocks = counts.get("locked" if not unlock else "unlocked", 0)
    nstarted = counts.get("already_started", 0)
    nraced = counts.get("raced", 0)
    nstrange = counts.get("strange", 0)

    if unlock:
        print(f"{nlocks:d} .__lock files deleted")
        print(f"{nstrange:d} strange folders")
    else:
        print(f"{nlocks:d} .__lock files added")
        print(f"{nraced:d} times just lost the .__lock to some other process")
        print(f"{nstarted:d} runs were already started")
        print(f"{nstrange:d} strange folders")

    if not opts.do:
        print(
            "\nThis was just a simultation. Rerun with",
            clr("--do", attrs=["bold"]),
            "to lock/unlock the experiment for real.",
        )


def lock(unlock=False):
    """Main function for liftoff-lock."""
    opts = parse_options()
    if not is_experiment(opts.config_path):
        raise RuntimeError(f"{opts.config_path:s} is not a liftoff experiment")
    opts.experiment_path = opts.config_path
    change_experiment_lock_status(opts, unlock=unlock)
