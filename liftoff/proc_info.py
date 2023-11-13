""" Here we implement liftoff-procs and liftoff-abort
"""

from argparse import Namespace
import os
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
                
                print("TODO:")
                print("PRINTING LINE")
                print(cmdline)
                
                session_id = extract_session_id(cmdline)
                experiment_full_name = extract_experiment_name(cmdline, results_path)

                # Check if the process matches the experiment criteria
                if (experiment is not None 
                    and experiment_full_name is not None 
                    and experiment not in experiment_full_name):
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
            # Split the path into parts
            path_parts = part.split(os.path.sep)
            # Assuming the experiment name is the directory right after results_path
            if results_path in path_parts:
                return path_parts[path_parts.index(results_path) + 1]
    return None


def display_procs(running):
    """Display the running liftoff processes."""
    for experiment_name, details in running.items():
        print(clr(experiment_name, attrs=["bold"]))
        for info in details:
            nrunning = clr(f"{len(info['procs']):d}", color="blue", attrs=["bold"])
            
            # Handling potential None values for ppid and session
            ppid_str = f"{info['ppid']:5d}" if info['ppid'] is not None else "N/A"
            session_str = info['session'] if info['session'] is not None else "N/A"

            ppid_formatted = clr(ppid_str, color="red", attrs=["bold"])
            print(f"   {ppid_formatted} :: {session_str} :: {nrunning} running")
            
            for pid, name in info["procs"]:
                # Assuming pid and name are always valid
                print(f"      - {pid:5d} :: {name}")


def procs() -> None:
    """Entry point for liftoff-procs."""

    opts = parse_options()
    display_procs(get_running_liftoffs(opts.experiment, opts.results_path))
