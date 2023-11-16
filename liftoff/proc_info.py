""" Here we implement liftoff-procs.
"""

from argparse import Namespace
import os
import psutil
from termcolor import colored as clr
from .common.options_parser import OptionParser


def parse_options() -> Namespace:
    """Parse command line arguments and liftoff configuration."""

    opt_parser = OptionParser(
        "liftoff-procs",
        ["experiment", "all", "timestamp_fmt", "results_path", "do"],
    )
    return opt_parser.parse_args()


def get_running_liftoffs():
    """Get the running liftoff processes."""
    running = {}

    for proc in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            cmdline = proc.cmdline()
            # Check if 'liftoff' is part of the command line
            if any("liftoff" in cmd_part for cmd_part in cmdline):
                session_id = extract_session_id(cmdline)
                if not session_id:
                    continue

                experiment_name, sub_experiment_name = extract_experiment_name(cmdline)

                # Aggregate subprocesses under the parent process
                parent_pid = proc.ppid()
                subprocess_info = (proc.pid, sub_experiment_name)
                # Add main experiments
                if experiment_name not in running:
                    running[experiment_name] = {}
                    
                # Add the pid associated with the main experiment
                if parent_pid not in running[experiment_name]:
                    running[experiment_name][parent_pid] = {
                        "session": session_id,
                        "procs": [],
                    }
                    
                # Add subexperiments
                running[experiment_name][parent_pid]["procs"].append(subprocess_info)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return running


def extract_session_id(cmdline):
    """Extract session ID from the command line arguments."""
    try:
        # Find the index of '--session-id' in the command line arguments
        index = cmdline.index("--session-id")
        # Return the element following '--session-id', which is the session ID
        return cmdline[index + 1] if index < len(cmdline) - 1 else None
    except ValueError:
        # '--session-id' not found in cmdline
        return None


def extract_experiment_name(cmdline):
    """Extract experiment name from the command line arguments."""
    for part in cmdline:
        if part.endswith(".yaml"):
            path_parts = part.split(os.path.sep)
            # Assuming the main experiment name is two levels up from the .yaml file
            main_experiment = path_parts[-4]
            # Assuming the sub-experiment names are one and two levels up from the .yaml file
            sub_experiment_1 = path_parts[-3]
            sub_experiment_2 = path_parts[-2]
            return main_experiment, f"{sub_experiment_1}{os.path.sep}{sub_experiment_2}"
    return None, None


def display_procs(running):
    """Display the running liftoff processes."""
    if running:
        for experiment_name, parent_procs in running.items():
            print(clr(experiment_name, attrs=["bold"]))
            for ppid, info in parent_procs.items():
                nrunning = clr(f"{len(info['procs']):d}", color="blue", attrs=["bold"])
                ppid_formatted = clr(f"{ppid:5d}", color="red", attrs=["bold"])
                session_str = info["session"] if info["session"] is not None else "N/A"
                print(f"   {ppid_formatted} :: {session_str} :: {nrunning} running")
                for pid, name in info["procs"]:
                    print(f"      - {pid:5d} :: {name}")
    else:
        print("No running liftoff processes.")


def procs() -> None:
    """Entry point for liftoff-procs."""

    display_procs(get_running_liftoffs())
