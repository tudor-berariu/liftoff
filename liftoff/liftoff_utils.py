import os
import time
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
        f"for p in `pgrep -f 'liftoff[[:blank:]]'`;"
        f" do ps -p $p -o pid,cmd h; done",
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

        procs.append((pid, experiment))

    return procs


def get_active_children(ppid: PID,
                        timestamp: Optional[Timestamp]
                        )-> Tuple[Timestamp, List[PID]]:
    cmd = f"for p in `pgrep -f '"
    if timestamp:
        cmd += f"\\-\\-timestamp {timestamp:s}"
    cmd += f" \\-\\-ppid {ppid:d}'`; do ps -p $p -o pid,ppid,cmd h; done"

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
        if int(parts[1]) != 1:
            continue
        if "--timestamp" not in parts:
            print("Strange command: ", line)
            continue
        pids.append(int(parts[0]))
        timestamps.append(parts[parts.index("--timestamp") + 1])

    timestamps = set(timestamps)

    if len(timestamps) > 1:
        print(f"This is strange! Multiple timestamps for PPID={ppid:d}!")
        assert False
    if timestamp and not pids:
        return None, []
    if not timestamps:
        print(f"No timestamps for PPID={ppid:d}!")
    return list(timestamps)[0], pids


def ask_user():
    check = str(input("Question ? (Y/N): ")).lower().strip()
    try:
        if check[0] == 'y':
            return True
        elif check[0] == 'n':
            return False
        else:
            print('Invalid Input')
            return ask_user()
    except Exception as error:
        print("Please enter valid inputs")
        print(error)
        return ask_user()


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
            ["PID", "Timestamp", "Experiment", "Active", "Done", "Total",
             "Parallelism", "Avg. time", "Time left"]}
    for ppid, timestamp, experiment, pids in get_status(timestamp, experiment):
        data["PID"].append(ppid)
        data["Timestamp"].append(timestamp)
        data["Experiment"].append(experiment)
        data["Active"].append(len(pids))

        exp_dirs = [d for d in os.listdir('results') if timestamp in d]
        assert len(exp_dirs) == 1
        exp_dir = exp_dirs[0]

        total, done, crashed, active = 0, 0, 0, 0
        total_time, active_elapsed = 0, 0
        min_time = None
        for rel_path, dirs, files in os.walk(os.path.join('results', exp_dir)):
            if not dirs:
                total += 1
                # os.path.join('results', exp_dir, rel_path)
                run_path = rel_path
                if ".__start" in files:
                    with open(os.path.join(run_path, ".__start")) as s_file:
                        start_time = int(s_file.readline().strip())
                        if min_time is None or min_time > start_time:
                            min_time = start_time
                    if ".__end" in files:
                        done += 1
                        with open(os.path.join(run_path, ".__end")) as e_file:
                            end_time = int(e_file.readline().strip())
                        total_time += end_time - start_time
                    elif ".__crash" in files:
                        crashed += 1
                        with open(os.path.join(run_path, ".__crash")) as e_file:
                            end_time = int(e_file.readline().strip())
                        total_time += end_time - start_time
                    else:
                        active += 1
                        active_elapsed += int(time.time()) - start_time

        wall_time = int(time.time()) - min_time
        total_run_time = total_time + active_elapsed
        factor = float(total_run_time) / wall_time
        data["Parallelism"].append(factor)
        if done + crashed > 0:
            avg_time = float(total_time) / (done + crashed)
            data["Avg. time"].append(avg_time)
            left_no = total - done - crashed
            data["Time left"].append(
                (left_no * avg_time - active_elapsed) / factor)
        else:
            data["Avg. time"].append(None)
            data["Time left"].append(None)

        data["Done"].append(done)
        data["Total"].append(total)

    print(tabulate.tabulate(data, headers="keys"))


def status()-> None:
    args = parse_args()
    display_progress(args.timestamp, args.experiment)


if __name__ == "__main__":
    display_progress()
