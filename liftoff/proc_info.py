""" Here we implement liftoff-procs and liftoff-abort
"""

from argparse import Namespace
import os.path
import subprocess
import psutil
from termcolor import colored as clr
from .common.options_parser import OptionParser


def parse_options() -> Namespace:
    """Parse command line arguments and liftoff configuration."""

    opt_parser = OptionParser(
        "liftoff-status",
        ["experiment", "all", "timestamp_fmt", "results_path", "do"],
    )
    return opt_parser.parse_args()


def get_running_liftoffs(experiment: str, results_path: str):
    """Get the running liftoff processes."""
    running = {}

    for proc in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            cmdline = proc.cmdline()
            # Check if 'liftoff' is part of the command line
            if any("liftoff" in cmd_part for cmd_part in cmdline):
                session_id = extract_session_id(cmdline)
                experiment_full_name = extract_experiment_name(cmdline, results_path)

                # Check if the process matches the experiment criteria
                if experiment is not None and experiment not in experiment_full_name:
                    continue

                proc_info = {
                    "session": session_id,
                    "ppid": proc.ppid(),
                    "procs": [(proc.pid, experiment_full_name)],
                }

                running.setdefault(experiment_full_name, []).append(proc_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return running


def extract_session_id(cmdline):
    """Extract session ID from the command line arguments."""
    for part in cmdline:
        if part.startswith("--session-id"):
            return part.split("=")[1]
    return None


def extract_experiment_name(cmdline, results_path):
    """Extract experiment name from the command line arguments."""
    for part in cmdline:
        if results_path in part:
            path_parts = part.split("/")
            # Assuming the experiment name is the directory right after results_path
            return path_parts[path_parts.index(results_path) + 1]
    return None


def display_procs(running):
    """Display the running liftoff processes."""
    for experiment_name, details in running.items():
        print(clr(experiment_name, attrs=["bold"]))
        for info in details:
            nrunning = clr(f"{len(info['procs']):d}", color="blue", attrs=["bold"])
            ppid = clr(f"{info['ppid']:5d}", color="red", attrs=["bold"])
            print(f"   {ppid:s}" f" :: {info['session']:s}" f" :: {nrunning:s} running")
            for pid, name in info["procs"]:
                print(f"      - {pid:5d} :: {name:s}")


def procs() -> None:
    """Entry point for liftoff-procs."""

    opts = parse_options()
    display_procs(get_running_liftoffs(opts.experiment, opts.results_path))
