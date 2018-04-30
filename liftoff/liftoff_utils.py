import os
import time
from argparse import ArgumentParser, Namespace
from typing import List, Optional, NamedTuple
import subprocess
from collections import OrderedDict
from termcolor import colored as clr
import tabulate

Args = Namespace
PID = int


class Experiment(NamedTuple):
    ppid: PID
    experiment: str
    timestamp: str
    root_path: str
    mode: str
    pids: str
    is_running: bool = True


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
        "-r", "--resumed", action="store_true", dest="short",
        help="Display short table.")
    arg_parser.add_argument(
        "-s", "--sort", dest="sort", default=None,
        help="Sort by column.")

    return arg_parser.parse_args()


# -- Code for running processes

def get_running_liftoffs(timestamp: Optional[str],
                         experiment: Optional[str])-> List[Experiment]:

    if not os.listdir('results'):
        return []

    cmd = "COLUMNS=0 pgrep liftoff" \
        " | xargs -r -n 1 grep --files-with-matches results/*/.__ppid -e" \
        " | xargs -n 1 -r dirname" \
        " | xargs -n 1 -r -I_DIR -- " \
        "sh -c 'echo _DIR" \
        " $(cat _DIR/.__ppid)" \
        " $(cat _DIR/.__mode)" \
        " $(cat _DIR/.__timestamp)" \
        " $(echo _DIR | cut -f2- -d_)'"

    result = subprocess.run(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)

    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))

    running = []
    for line in result.stdout.decode("utf-8").split("\n"):
        if not line:
            continue
        (path, ppid, mode, tmstmp, exp) = line.split()
        if experiment and experiment != exp:
            continue
        if timestamp and timestamp != tmstmp:
            continue
        if mode == "single":
            pids = []
        elif mode == "multiprocess":
            result = subprocess.run(f"ps --ppid {ppid:s} -o pid h",
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True)
            if result.stderr:
                raise Exception(result.stderr.decode("utf-8"))
            pids = [int(l.strip())
                    for l in result.stdout.decode("utf-8").split("\n") if l]
        elif mode == "nohup":
            cmd = f"for p in "\
                  f"`pgrep -f '\\-\\-timestamp {tmstmp:s} \\-\\-ppid {ppid:s}'`"\
                  f"; do COLUMNS=0 ps -p $p -o pid,ppid h; done"

            result = subprocess.run(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True)
            if result.stderr:
                raise Exception(result.stderr.decode("utf-8"))
            pids = []
            for line1 in result.stdout.decode("utf-8").split("\n"):
                if not line1:
                    continue

                [pid, _ppid] = list(map(int, line1.split()))
                if _ppid == 1:
                    pids.append(pid)

        running.append(Experiment(int(ppid), exp, tmstmp, path, mode, pids))

    return running


WHAT_TO_SORT = {"time": "T",
                "experiment": "experiment"}


def get_all_from_results(timestamp: Optional[str],
                         experiment: Optional[str])-> List[Experiment]:
    experiments = get_running_liftoffs(timestamp, experiment)
    cmd = "COLUMNS=0 find results/*/.__timestamp 2>/dev/null" \
        " | xargs -n 1 -r dirname" \
        " | xargs -n 1 -r -I_DIR -- " \
        "sh -c 'echo _DIR" \
        " $(cat _DIR/.__mode)" \
        " $(cat _DIR/.__timestamp)" \
        " $(echo _DIR | cut -f2- -d_)'"

    result = subprocess.run(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)

    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))

    running_timestamps = [e.timestamp for e in experiments]

    for line in result.stdout.decode("utf-8").split("\n"):
        if not line:
            continue
        (path, mode, tmstmp, exp) = line.split()
        if experiment and experiment != exp:
            continue
        if timestamp and timestamp != tmstmp:
            continue
        if tmstmp in running_timestamps:
            continue
        experiments.append(Experiment(-1, exp, tmstmp, path, mode, [], False))

    return experiments


def display_progress(experiments: List[Experiment], args: Args = None):
    headers = ["PID", "Timestamp", "Experiment",
               "Running", "Done", "Crashed", "Lost", "Total", "Success",
               "Px", "Avg.time", "T", "Time left",
               "Obs"]
    exp_info = {info: [] for info in headers}

    for experiment in experiments:
        exp_info["PID"].append(experiment.ppid)
        exp_info["Timestamp"].append(experiment.timestamp)
        exp_info["Experiment"].append(
            clr(experiment.experiment, 'yellow', attrs=['bold']))

        comment_file_path = os.path.join(experiment.root_path, ".__comment")
        if os.path.isfile(comment_file_path):
            with open(comment_file_path, "r") as comment_file:
                exp_info["Obs"].append(comment_file.read())

        if experiment.is_running:
            if experiment.mode == "single":
                running = 1
            else:
                running = len(experiment.pids)
        else:
            running = 0

        total, success, crashed, active = 0, 0, 0, 0
        total_time, active_elapsed = 0, 0
        min_time = None
        max_time = None
        for rel_path, _, files in os.walk(experiment.root_path):
            if ".__leaf" in files:
                total += 1
                # os.path.join('results', exp_dir, rel_path)
                run_path = rel_path
                if ".__start" in files:
                    with open(os.path.join(run_path, ".__start")) as s_file:
                        start_time = int(s_file.readline().strip())
                        if min_time is None or min_time > start_time:
                            min_time = start_time
                    if ".__end" in files:
                        success += 1
                        with open(os.path.join(run_path, ".__end")) as e_file:
                            end_time = int(e_file.readline().strip())
                        if max_time is None or max_time < end_time:
                            max_time = end_time
                        total_time += end_time - start_time
                    elif ".__crash" in files:
                        crashed += 1
                        with open(os.path.join(run_path, ".__crash")) as e_file:
                            end_time = int(e_file.readline().strip())
                        if max_time is None or max_time < end_time:
                            max_time = end_time
                        total_time += end_time - start_time
                    else:
                        active += 1
                        active_elapsed += int(time.time()) - start_time

        done = crashed + success
        lost = active - running

        if running > 0:
            wall_time = int(time.time()) - min_time
        elif min_time and max_time:
            wall_time = max_time - min_time
        else:
            wall_time = 0

        total_run_time = total_time + active_elapsed
        if wall_time > 0 and lost == 0:
            factor = float(total_run_time) / wall_time
        else:
            factor = None
        exp_info["Px"].append(factor)

        if done + crashed > 0:
            avg_time = float(total_time) / done
            exp_info["Avg.time"].append(avg_time)
            left_no = total - done
            if factor and factor > 0 and lost == 0:
                exp_info["Time left"].append(
                    (left_no * avg_time - active_elapsed) / factor)
                exp_info["T"].append(avg_time / factor)
            else:
                exp_info["Time left"].append(None)
                exp_info["T"].append(None)
        else:
            exp_info["Avg.time"].append(None)
            exp_info["Time left"].append(None)
            exp_info["T"].append(None)

        exp_info["Running"].append(running)
        exp_info["Crashed"].append(crashed)
        exp_info["Lost"].append(lost)
        exp_info["Success"].append(success)
        exp_info["Done"].append(done)
        exp_info["Total"].append(total)

    fkey = f"{clr('R', 'yellow'):s} + " \
           f"{clr('C', 'red'):s} + " \
           f"{clr('L', 'blue'):s} + " \
           f"{clr('S', 'green', attrs=['bold']):s} = " \
           f"{clr('Done', attrs=['bold']):s} / " \
           f"{clr('Total', attrs=['bold']):s}"

    if exp_info["Running"]:
        f_r = max(len(f'{r:d}') for r in exp_info['Running'])
        f_c = max(len(f'{c:d}') for c in exp_info['Crashed'])
        f_l = max(len(f'{l:d}') for l in exp_info['Lost'])
        f_s = max(len(f'{s:d}') for s in exp_info['Success'])
        f_d = max(len(f'{d:d}') for d in exp_info['Done'])
        f_t = max(len(f'{t:d}') for t in exp_info['Total'])

        counts = zip(*[exp_info[l]
                       for l in ["Running", "Crashed", "Lost", "Success",
                                 "Done", "Total"]])

        exp_info[fkey] = [f"{clr(f'{r:{f_r}d}', 'yellow'):s} + "
                          f"{clr(f'{c:{f_c}d}', 'red'):s} + "
                          f"{clr(f'{l:{f_l}d}', 'blue'):s} + "
                          f"{clr(f'{s:{f_s}d}', 'green', attrs=['bold']):s} = "
                          f"{clr(f'{d:{f_d}d}', attrs=['bold']):s} / "
                          f"{clr(f'{t:{f_t}d}', attrs=['bold']):s}"
                          for (r, c, l, s, d, t) in counts]
    else:
        exp_info[fkey] = []

    del exp_info["Running"]
    del exp_info["Crashed"]
    del exp_info["Lost"]
    del exp_info["Success"]
    del exp_info["Done"]
    del exp_info["Total"]

    if not any(x for x in exp_info["Obs"]):
        del exp_info["Obs"]

    if args and args.short:
        headers = ["Timestamp", "Experiment", fkey]
    else:
        headers = ["PID", "Timestamp", "Experiment",
                   fkey, "Time left",
                   "Px", "Avg.time", "T"]

    if "Obs" in exp_info:
        headers.append("Obs")

    if args and args.sort:
        column = WHAT_TO_SORT[args.sort]
        values = exp_info[column]
        if column in ["T", "Avg.time", "Done", "Px"]:
            def key(x):
                return x[1] if x[1] else float("inf")
        else:
            def key(x):
                return x[1] if x[1] is not None else ""
        sorted_values = sorted(enumerate(values), key=key)
        new_indices = [idx for (idx, _) in sorted_values]
        exp_info = {key: [values[i] for i in new_indices]
                    for (key, values) in exp_info.items()}

    o_data = OrderedDict([(key, exp_info[key]) for key in headers])

    print(tabulate.tabulate(o_data, headers="keys"))
    print('--')
    print(f"{clr('R', 'yellow'):s} = {clr('Running', 'yellow'):s}; "
          f"{clr('C', 'red'):s} = {clr('Crashed', 'red'):s} "
          f"{clr('L', 'blue'):s} = {clr('Lost', 'blue'):s}; "
          f"{clr('S', 'green', attrs=['bold']):s} = "
          f"{clr('Success', 'green', attrs=['bold']):s}")
    print("If there are lost experiments, 'Px', and 'Time left' might be wrong.")


def ask_user(experiments: List[Experiment], to_kill: List[PID]):
    display_progress(experiments)
    b_to_kill = [clr(t, 'yellow', attrs=['bold']) for t in to_kill]
    answer = str(input(f"\nAre you sure you want to kill "
                       f"{', '.join(b_to_kill):s}?"
                       f" (y/n): ")).lower().strip()
    try:
        if answer[0] == 'y':
            return True
        elif answer[0] == 'n':
            return False
        return ask_user(experiments, to_kill)
    except Exception as error:
        print(error)
        return ask_user(experiments, to_kill)


def kill_all(experiment: Experiment):
    cmd = f"kill {experiment.ppid:d}"
    result = subprocess.run(cmd, stderr=subprocess.PIPE, shell=True)
    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))

    if experiment.mode in ["single", "multiprocess"]:
        return

    cmd = f"for p in `pgrep -f '"
    cmd += f"\\-\\-timestamp {experiment.timestamp:s}"
    cmd += f" \\-\\-ppid {experiment.ppid:d}'`; do kill $p; done"

    result = subprocess.run(cmd, stderr=subprocess.PIPE, shell=True)
    if result.stderr:
        raise Exception(result.stderr.decode("utf-8"))


def status()-> None:
    args = parse_args()
    if not args.all:
        experiments = get_running_liftoffs(args.timestamp, args.experiment)
    else:
        experiments = get_all_from_results(args.timestamp, args.experiment)
    display_progress(experiments, args)


def abort() -> None:
    args = parse_args()
    experiments = get_running_liftoffs(args.timestamp, args.experiment)
    if len(experiments) > 1 and not args.all:
        latest_tmstmp = max(e.timestamp for e in experiments)
        to_kill = [latest_tmstmp]
    else:
        to_kill = [e.timestamp for e in experiments]

    if not to_kill:
        print("Nothing to murder here.")
        return

    if ask_user(experiments, to_kill):
        for exp in experiments:
            if exp.timestamp in to_kill:
                print(f"Killing {exp.experiment:s}_{exp.timestamp:s} "
                      f"(PID={exp.ppid:d})!")
                kill_all(exp)
