""" Here we implement liftoff-abort.
"""

from argparse import Namespace
import os
import subprocess
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
    escaped_sid = session_id.replace("-", r"\-")
    cmd = (
        f"for p in "
        f"`pgrep -f '\\-\\-session\\-id {escaped_sid:s}'`"
        f"; do COLUMNS=0 ps -p $p -o pid,ppid,cmd h; done"
    )
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True
    )
    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))

    pids = []
    for line1 in result.stdout.decode("utf-8").split("\n"):
        if not line1:
            continue

        pid, fake_ppid, *other = line1.split()
        pid, fake_ppid = int(pid), int(fake_ppid)
        if fake_ppid != 1:
            good = not any(".__crash" in p for p in other)
            if good:
                pids.append(pid)
    return pids


def abort_experiment(ppid, results_path):
    """ Here we search for running pids.
    """

    cmd = f"COLUMNS=0 ps -o cmd= -f {ppid:d}"
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True
    )
    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))

    (lcmd,) = result.stdout.decode("utf-8").strip().split("\n")

    found = False
    for arg in lcmd.split():
        if is_experiment(arg):
            found = True
            break

    if not found:
        print(lcmd)
        return

    experiment_name = None
    found = False
    with os.scandir(results_path) as fit:
        for entry in fit:
            if not is_experiment(entry.path):
                continue
            experiment_name = entry.name
            with os.scandir(entry.path) as fit2:
                for entry2 in fit2:
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
        print(
            "Run", clr("liftoff-procs", attrs=["bold"]), "to see running liftoffs.",
        )
        return

    pids = running_children(session_id)
    nrunning = clr(f"{len(pids):d}", color="blue", attrs=["bold"])
    cppid = clr(f"{ppid:5d}", color="red", attrs=["bold"])
    name = clr(f"{experiment_name:s}::{session_id:s}", attrs=["bold"])

    print(f"\nWill kill {nrunning:s} subprocesses from {name} ({cppid:s}).")
    if not ask_user():
        return

    pids = running_children(session_id)

    cmd = f"kill {ppid:d} " + " ".join([str(p) for p in pids])

    result = subprocess.run(cmd, stderr=subprocess.PIPE, shell=True, check=True)
    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))

    print("The eagle is down! Mission accomplished.")


def abort():
    """ Main function.
    """

    opts = parse_options()
    abort_experiment(opts.pid, opts.results_path)
