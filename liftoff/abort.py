""" Here we implement liftoff-abort.
"""

from argparse import Namespace
import os
import subprocess
import psutil
from termcolor import colored as clr

from .common.experiment_info import is_experiment
from .common.options_parser import OptionParser


def parse_options() -> Namespace:
    """Parse command line arguments and liftoff configuration."""

    opt_parser = OptionParser("liftoff-abort", ["pid", "results_path", "skip_confirmation"])
    return opt_parser.parse_args()


def ask_user():
    answer = input("\nAre you sure you want to kill them? (Y/n) ").lower().strip()

    # If the answer is empty or 'yes' (or just 'y'), return True
    if answer == "" or answer.startswith("y"):
        return True
    # Otherwise, default to False
    return False


def running_children(session_id):
    """Gets running processes with a specific session-id.
    TODO: check more details.
    """
    """ Gets running processes with a specific session-id."""
    session_id_flag = f"--session-id {session_id}"
    pids = []

    for proc in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"]
            # Ensure cmdline is a list before joining
            if isinstance(cmdline, list):
                cmdline_str = " ".join(cmdline)
            else:
                continue  # Skip this process if cmdline is not a list

            # Check if the session id flag is in the command line arguments
            if session_id_flag in cmdline_str:
                # Check if the process has not crashed
                if not any(".__crash" in arg for arg in cmdline):
                    pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return pids


def abort_experiment(ppid, results_path, skip_confirmation=False):
    """Terminate a running experiment and its subprocesses."""
    try:
        parent_process = psutil.Process(ppid)
    except psutil.NoSuchProcess:
        print("No process found with PID", ppid)
        return

    # Check if the parent process is part of an experiment
    found = False
    for arg in parent_process.cmdline():
        if is_experiment(arg):
            found = True
            break

    if not found:
        print(f"Found pid {ppid}, but it's not the main experiment:")
        print(" ".join(parent_process.cmdline()))
        return

    # Find the experiment name and session ID
    experiment_name, session_id = None, None
    found = False
    with os.scandir(results_path) as fit:
        for entry in fit:
            if not is_experiment(entry.path):
                continue
            experiment_name = entry.name
            for entry2 in os.scandir(entry.path):
                if entry2.name.startswith(".__"):
                    with open(entry2.path) as hndlr:
                        try:
                            candidate_pid = int(hndlr.readline().strip())
                            if candidate_pid == ppid:
                                found = True
                                session_id = entry2.name[3:]
                                break
                        except ValueError:
                            pass
            if found:
                break

    if not found:
        print("Couldn't find the process you want to kill.")
        return

    # Get the running child processes
    pids = running_children(session_id)
    print(
        f"\nWill kill {len(pids)} subprocesses from {experiment_name}::{session_id} (PID: {ppid})."
    )

    # We might want to skip the confirmation 
    # (when running the process from script)
    if not skip_confirmation:
        if not ask_user():
            return

    # Attempt to terminate the parent process and its children
    try:
        for pid in pids:
            child_proc = psutil.Process(pid)
            child_proc.terminate()  # or child_proc.kill() for a forceful termination
        parent_process.terminate()
    except Exception as e:
        print(f"Error terminating processes: {e}")

    # ( ͡° ͜ʖ ͡°)
    print("The eagle is down! Mission accomplished.")


def abort():
    """Main function."""

    opts = parse_options()
    abort_experiment(opts.pid, opts.results_path, opts.skip_confirmation)
