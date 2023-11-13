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
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser("liftoff-abort", ["pid", "results_path"])
    return opt_parser.parse_args()


def ask_user():
    answer = str(input("\nAre you sure you want to kill them? (y/n)")).lower().strip()

    if answer and answer[0] == "y":
        return True
    elif answer and answer[0] == "n":
        return False
    return ask_user()


def running_children(session_id):
    """ Gets running processes with a specific session-id.
        TODO: check more details.
    """
    session_id_flag = f"--session-id {session_id}"
    pids = []

    for proc in psutil.process_iter(['pid', 'ppid', 'cmdline']):
        try:
            # Check if the session id flag is in the command line arguments
            if session_id_flag in ' '.join(proc.info['cmdline']):
                # Check if the process has not crashed
                if not any(".__crash" in arg for arg in proc.info['cmdline']):
                    pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process no longer exists or access is denied, skip it
            continue

    return pids


def abort_experiment(ppid, results_path):
    """ Here we search for running pids.
    """

    try:
        parent_process = psutil.Process(ppid)
    except psutil.NoSuchProcess:
        print("No process found with PID", ppid)
        return

    # Check if the process is part of an experiment
    found = False
    for arg in parent_process.cmdline():
        if is_experiment(arg):
            found = True
            break

    if not found:
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
        print("Run liftoff-procs to see running liftoffs.")
        return

    # Get the running child processes
    pids = running_children(session_id)
    print(f"\nWill kill {len(pids)} subprocesses from {experiment_name}::{session_id} (PID: {ppid}).")

    # Ask user for confirmation (assuming ask_user() is a function that asks for user confirmation)
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

    print("The eagle is down! Mission accomplished. ( ͡° ͜ʖ ͡°)")


def abort():
    """ Main function.
    """

    opts = parse_options()
    abort_experiment(opts.pid, opts.results_path)
