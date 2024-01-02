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


def is_liftoff_main_process(cmdline):
    """Check if the process is a main liftoff process."""
    return "liftoff.exe" in " ".join(cmdline).lower()


def get_running_liftoffs():
    running = {}
    main_process_pids = set()

    # First pass: Identify all liftoff main processes
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.cmdline()
            if is_liftoff_main_process(cmdline):
                main_process_pids.add(proc.pid)
                running[proc.pid] = {
                    "procs": [],
                    "experiment": None,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Second pass: Associate subprocesses with main liftoff process
    for proc in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            parent_pid = proc.ppid()
            cmdline = proc.cmdline()
            if (
                "--session-id" in " ".join(cmdline).lower()
                and parent_pid in main_process_pids
            ):
                session_id = extract_session_id(cmdline)
                experiment_name, sub_experiment_name = extract_experiment_name(cmdline)
                subprocess_info = {
                    "pid": proc.pid,
                    "session_id": session_id,
                    "experiment_name": sub_experiment_name,
                }
                running[parent_pid]["procs"].append(subprocess_info)

                # Optionally update the experiment name for the main process
                if not running[parent_pid]["experiment"] and experiment_name:
                    running[parent_pid]["experiment"] = experiment_name
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return running


def extract_session_id(cmdline):
    """Extract session ID from the command line arguments."""
    cmdline_str = " ".join(cmdline)  # Convert cmdline list to a single string
    try:
        # Split the command line string by spaces and search for '--session-id'
        parts = cmdline_str.split()
        if "--session-id" in parts:
            index = parts.index("--session-id")
            return parts[index + 1] if index < len(parts) - 1 else None
    except ValueError:
        pass
    return None


def extract_experiment_name(cmdline):
    """Extract experiment name from the command line arguments."""
    cmdline_str = " ".join(cmdline)
    try:
        # Find the part of the command line string that ends with '.yaml'
        yaml_path = next(
            (part for part in cmdline_str.split() if part.endswith(".yaml")), None
        )
        if yaml_path:
            path_parts = yaml_path.split(os.path.sep)
            main_experiment = path_parts[-4]
            sub_experiment_1 = path_parts[-3]
            sub_experiment_2 = path_parts[-2]
            return main_experiment, f"{sub_experiment_1}{os.path.sep}{sub_experiment_2}"
    except IndexError:
        # Handle cases where the path does not have the expected number of parts
        print(f"Warning: Unexpected path format for experiment in cmdline: {cmdline}")
    return None, None


def display_procs(running):
    """Display the running liftoff processes."""
    if running:
        for main_pid, main_proc_info in running.items():
            # Format the main process ID
            main_pid_formatted = clr(f"{main_pid:5d}", color="red", attrs=["bold"])
            experiment_name = main_proc_info.get("experiment", "N/A")
            
            # Print the main process information
            print(f"{main_pid_formatted} :: {experiment_name} :: {len(main_proc_info['procs'])} running")

            # Iterate and display each subprocess
            for subproc in main_proc_info["procs"]:
                sub_pid = subproc.get("pid")
                session_id = subproc.get("session_id", "N/A")
                sub_experiment_name = subproc.get("experiment_name", "N/A")

                # Format the subprocess information
                sub_pid_formatted = clr(f"{sub_pid:5d}", color="blue", attrs=["bold"])
                print(f"      - {sub_pid_formatted} :: {sub_experiment_name}")
    else:
        print("No running liftoff processes.")


def procs() -> None:
    """Entry point for liftoff-procs."""

    display_procs(get_running_liftoffs())
