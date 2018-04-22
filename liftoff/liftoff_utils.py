import os
from argparse import ArgumentParser, Namespace
from typing import List, Optional, Tuple
import subprocess
import tabulate

Args = Namespace
PID = int
Timestamp = str


def parse_args() -> Args:
    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "-a", "--all", action="store_true", dest="all",
        help="Apply to all running experiments.")
    arg_parser.add_argument(
        "-e", "--experiment", type=str, dest="experiment",
        help="Get by name.")
    arg_parser.add_argument(
        "-t", "--timestamp", type=str, dest="timestamp",
        help="Get by timestamp.")
    arg_parser.add_argument(
        "-n", "--no-action", action="store_true", dest="no_action",
        help="Display commands, but take do not execute them.")

    return arg_parser.parse_args()


def get_liftoff_processes()-> List[Tuple[PID, Optional[str]]]:
    result = subprocess.run(
        f"for p in `pgrep liftoff`; do ps -p $p -o pid,cmd h; done",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=True)

    if result.stderr:
        assert False, result.stderr.decode("utf-8")

    procs = []
    for line in result.stdout.decode("utf-8").split('\n'):
        if not line:
            continue
        parts = line.split()
        pid = int(parts[0])
        experiment: Optional[str] = None
        if "-e" in parts:
            experiment = parts[parts.index("-e") + 1]
        elif "--experiment" in parts:
            experiment = parts[parts.index("--experiment") + 1]

        procs.append(pid, experiment)

    return procs


def get_active_children(ppid: PID,
                        timestamp: Optional[Timestamp]
                        )-> Tuple[Timestamp, List[PID]]:
    cmd = f"for p in `pgrep -f '\\-\\-ppid {ppid:d}"
    if timestamp:
        cmd += f" \\-\\-timestamp {timestamp:s}"
    cmd += "'`; do ps -p $p -o pid,cmd h; done"

    result = subprocess.run(cmd,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            shell=True)
    if result.stderr:
        assert False, result.stderr.decode("utf-8")
    timestamps = []
    pids = []
    for line in result.stdout.decode("utf-8").split('\n'):
        if not line:
            continue
        parts = line.split()
        pids.append(int(parts[0]))
        timestamps.append(parts[parts.index("--timestamp") + 1])
    timestamps = set(timestamps)
    if len(timestamps) > 1:
        print("This is strange! Multiple timestamps for PPID={ppid:d}!")
        assert False
    return list(timestamps)[0], pids


def get_status(timestamp: Optional[Timestamp] = None,
               experiment: Optional[str] = None
               ) -> List[Tuple[PID, Timestamp, str, List[PID]]]:
    results = []
    for ppid, exp in get_liftoff_processes():
        if experiment and experiment != exp:
            continue
        tstamp, pids = get_active_children(ppid, timestamp)
        if timestamp and timestamp != tstamp:
            continue
        results.append((ppid, tstamp, exp, pids))
    return results


def display_progress(timestamp: Optional[Timestamp] = None,
                     experiment: Optional[str] = None) -> None:
    data = {h: [] for h in
            ["PID", "Timestamp", "Experiment", "Active", "Done", "Total"]}
    for ppid, timestamp, experiment, pids in get_status(timestamp, experiment):
        data["PID"] = ppid
        data["Timestamp"] = timestamp
        data["experiment"] = experiment
        data["Active"] = len(pids)

        dirs = [d for d in os.listdir('./results/') if timestamp in d]
        assert len(dirs) == 1

        total_no, done_no = 0, 0
        for _, dirs, files in os.walk(os.path.join('./results/', dirs[0])):
            if not dirs:
                total_no += 1
                done_no += ("results.pkl" in files)
        data["Done"] = done_no
        data["Total"] = total_no

    print(tabulate.tabulate(data))


if __name__ == "__main__":
    display_progress()
