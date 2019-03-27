""" Here we implement liftoff-procs and liftoff-abort
"""

from argparse import Namespace
import os.path
import subprocess
from termcolor import colored as clr
from .common.options_parser import OptionParser


def parse_options() -> Namespace:
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser(
        "liftoff-status",
        ["experiment", "all", "timestamp_fmt", "results_path", "do"],
    )
    return opt_parser.parse_args()


def get_running_liftoffs(experiment: str, results_path: str):
    """ Get the running liftoff processes.
    """

    cmd = (
        "COLUMNS=0 pgrep liftoff"
        " | xargs -r -n 1 grep "
        f"--files-with-matches {results_path:s}/*/.__* -e"
    )
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))

    running = {}

    for session_path in result.stdout.decode("utf-8").split("\n"):
        if not session_path:
            continue
        with open(session_path) as hndlr:
            ppid = int(hndlr.readline().strip())

        experiment_full_name = os.path.basename(os.path.dirname(session_path))

        if experiment is not None and experiment not in experiment_full_name:
            continue

        proc_group = dict({})
        session_id = os.path.basename(session_path)[3:]

        escaped_sid = session_id.replace("-", r"\-")
        cmd = (
            f"for p in "
            f"`pgrep -f '\\-\\-session\\-id {escaped_sid:s}'`"
            f"; do COLUMNS=0 ps -p $p -o pid,ppid,cmd h; done"
        )
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
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
                cfg = ""
                for part in other:
                    if part.endswith("cfg.yaml"):
                        cfg = (
                            os.path.basename(
                                os.path.dirname(os.path.dirname(part))
                            )
                            + "/"
                            + os.path.basename(os.path.dirname(part))
                        )
                        break
                pids.append((pid, cfg))

        proc_group["session"] = session_id
        proc_group["ppid"] = ppid
        proc_group["procs"] = pids

        running.setdefault(experiment_full_name, []).append(proc_group)

    return running


def display_procs(running):
    """ Display the running liftoff processes.
    """
    for experiment_name, details in running.items():
        print(clr(experiment_name, attrs=["bold"]))
        for info in details:
            nrunning = clr(
                f"{len(info['procs']):d}", color="blue", attrs=["bold"]
            )
            ppid = clr(f"{info['ppid']:5d}", color="red", attrs=["bold"])
            print(
                f"   {ppid:s}"
                f" :: {info['session']:s}"
                f" :: {nrunning:s} running"
            )
            for pid, name in info["procs"]:
                print(f"      - {pid:5d} :: {name:s}")


def procs() -> None:
    """ Entry point for liftoff-procs.
    """

    opts = parse_options()
    display_procs(get_running_liftoffs(opts.experiment, opts.results_path))
