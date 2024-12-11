""" Here we implement liftoff-procs.
"""

from argparse import Namespace
import os, sys
import psutil
import re
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
    cmd_str = " ".join(cmdline).lower()
    if sys.platform.startswith('win'):
        return 'liftoff.exe' in cmd_str
    else:
        # Regex pattern to match 'liftoff' not followed by '-procs'
        pattern = r'/liftoff(?!\-procs)\b'
        return re.search(pattern, cmd_str) is not None

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


def extract_common_path(cmdline):
    # Assuming the path is the fourth argument in the main Liftoff process command line
    # Adjust the index based on your actual command line structure
    if len(cmdline) > 3:
        path = cmdline[3]
        # Normalize the path to ensure consistency
        return os.path.normpath(path)
    return None

def extract_subprocess_path(cmdline, common_path):
    # Extracting the path from subprocess command line
    for arg in cmdline:
        if common_path in arg:
            # Extract the segment of the path that matches the common_path
            path_segment = arg.split(common_path)[-1]
            return os.path.normpath(common_path + path_segment)
    return None

def get_running_liftoffs():
    running = {}
    main_process_pids = set()
    path_to_main_pid = {}
    unique_subprocess_keys = set()  # To store unique combinations of path and experiment name

    # First pass: Identify all liftoff main processes and map paths
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.cmdline()
            if is_liftoff_main_process(cmdline):
                main_process_pids.add(proc.pid)
                running[proc.pid] = {
                    "procs": [],
                    "experiment": None,
                }
                if not sys.platform.startswith('win'):  # Linux/WSL
                    common_path = extract_common_path(cmdline)
                    if common_path:
                        path_to_main_pid[common_path] = proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Second pass: Associate subprocesses
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.cmdline()
            proc_pid = proc.pid
            if proc_pid not in main_process_pids:  # Exclude main process PID
                parent_pid = None

                if sys.platform.startswith('win'):
                    # Windows: use parent PID for association
                    parent_pid = proc.ppid() if proc.ppid() in main_process_pids else None

                    if parent_pid:
                        experiment_name, sub_experiment_name = extract_experiment_name(cmdline)
                        unique_key = (proc_pid, sub_experiment_name)  # Unique key for Windows

                        if unique_key not in unique_subprocess_keys:
                            subprocess_info = {
                                "pid": proc_pid,
                                "experiment_name": sub_experiment_name,
                            }
                            running[parent_pid]["procs"].append(subprocess_info)
                            unique_subprocess_keys.add(unique_key)

                            if not running[parent_pid]["experiment"] and experiment_name:
                                running[parent_pid]["experiment"] = experiment_name
                                    
                else:
                    # Linux/WSL: focus on 'sh -c' processes
                    if 'sh' in cmdline and '-c' in cmdline:
                        for common_path, pid in path_to_main_pid.items():
                            subprocess_path = extract_subprocess_path(cmdline, common_path)
                            if subprocess_path and subprocess_path.startswith(common_path):
                                parent_pid = pid
                                break

                        if parent_pid:
                            experiment_name, sub_experiment_name = extract_experiment_name(cmdline)
                            unique_key = (subprocess_path, sub_experiment_name)
                            if unique_key not in unique_subprocess_keys:
                                subprocess_info = {
                                    "pid": proc_pid,
                                    "experiment_name": sub_experiment_name,
                                }
                                running[parent_pid]["procs"].append(subprocess_info)
                                unique_subprocess_keys.add(unique_key)

                                if not running[parent_pid]["experiment"] and experiment_name:
                                    running[parent_pid]["experiment"] = experiment_name

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return running


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
