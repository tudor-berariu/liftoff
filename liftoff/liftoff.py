from argparse import ArgumentParser, Namespace
from typing import Callable, List, Optional, Tuple
from copy import deepcopy
import os
import re
from importlib import import_module
import multiprocessing
import multiprocessing.pool
import time
import subprocess
import yaml
from termcolor import colored as clr

from .config import read_config, namespace_to_dict, config_to_string, value_of

Args = Namespace
PID = int


def parse_args() -> Args:
    """If you need GPU magic, please use detached processes."""

    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "module",
        default="learn.py",
        help="Module where to call `run(args)` from.")
    arg_parser.add_argument(
        '--runs-no',
        type=int,
        default=1,
        dest="runs_no"
    )
    arg_parser.add_argument(
        '--resume',
        default=False,
        action="store_true",
        dest="resume",
        help="Resume last experiment.")
    arg_parser.add_argument(
        "-p", "--procs-no",
        default=4,
        type=int,
        dest="procs_no",
        help="Number of concurrent processes.")
    arg_parser.add_argument(
        "-g", "--gpus",
        default=[],
        type=int,
        nargs="*",
        dest="gpus",
        help="GPUs to distribute processes to.")
    arg_parser.add_argument(
        "--per-gpu",
        default=0,
        type=int,
        dest="per_gpu",
        help="Visible GPUs.")
    arg_parser.add_argument(
        "--no-detach",
        default=False,
        action="store_true",
        dest="no_detach",
        help="do not detach; spawn processes from python")
    arg_parser.add_argument(
        "--env",
        type=str,
        dest="env",
        help="Conda environment.")
    arg_parser.add_argument(
        "--mkl",
        type=int,
        dest="mkl",
        default=0,
        help="Set MKL_NUM_THREADS. -1 not to change it.")
    arg_parser.add_argument(
        "--omp",
        type=int,
        dest="omp",
        default=0,
        help="Set OMP_NUM_THREADS. -1 not to change it.")
    return arg_parser.parse_known_args()[0]


def get_exp_args(cfgs: List[Args], root_path: str, runs_no: int) -> List[Args]:
    """Takes the configs read from files and augments them with
    out_dir, and run_id"""

    exp_args = []
    for j, cfg in enumerate(cfgs):
        title = cfg.title
        for char in " -.,=:;/()[]'":
            title = title.replace(char, "_")
        while "___" in title:
            title = title.replace("___", "__")

        alg_path = os.path.join(root_path, f"{j:d}_{title:s}")
        if not os.path.isdir(alg_path):
            os.makedirs(alg_path, exist_ok=True)

        if runs_no > 1:
            for run_id in range(runs_no):
                exp_path = os.path.join(alg_path, f"{run_id:d}")
                if os.path.isdir(exp_path):
                    results_file = os.path.join(exp_path, "results.pkl")
                    if os.path.isfile(results_file):
                        print(f"Skipping {cfg.title:s} <{run_id:d}>. "
                              f"{results_file:s} exists.")
                        continue
                else:
                    os.makedirs(exp_path)

                new_cfg = deepcopy(cfg)
                new_cfg.run_id = run_id
                new_cfg.out_dir = exp_path
                new_cfg.cfg_dir = exp_path
                exp_args.append(new_cfg)

                cfg_file = os.path.join(exp_path, "cfg.yaml")
                if not os.path.isfile(cfg_file):
                    with open(cfg_file, "w") as yaml_file:
                        yaml.safe_dump(namespace_to_dict(new_cfg), yaml_file,
                                       default_flow_style=False)

        else:
            # if there's a single run, no individual folders are created
            results_file = os.path.join(alg_path, "results.pkl")
            if os.path.isfile(results_file):
                print(f"Skipping {cfg.title:s}. {results_file:s} exists.")
            else:
                new_cfg = deepcopy(cfg)
                new_cfg.run_id = 0
                new_cfg.out_dir = alg_path
                new_cfg.cfg_dir = alg_path
                exp_args.append(new_cfg)

                cfg_file = os.path.join(alg_path, "cfg.yaml")
                if not os.path.isfile(cfg_file):
                    with open(cfg_file, "w") as yaml_file:
                        yaml.safe_dump(namespace_to_dict(cfg), yaml_file,
                                       default_flow_style=False)

    return exp_args


# --------------------------------------------
# Run experiments as locally spawned processes

def get_function(args: Args) -> Callable[[Args], None]:
    import sys
    sys.path.append(os.getcwd())
    module_name = args.module
    if module_name.endswith(".py"):
        module_name = module_name[:-3]
    module = import_module(module_name)
    assert "run" in module.__dict__, "Module must have function run(args)."
    return module.__dict__["run"]


def spawn_from_here(root_path: str, cfgs: List[Args], args: Args) -> None:

    # Figure out what should be executed
    function = get_function(args)

    assert not args.gpus, "Cannot specify GPUs unless you detach processes"
    assert args.procs_no >= 1, f"Strange number of procs: {args.procs_no:d}"

    class NoDaemonProcess(multiprocessing.Process):
        """
        Solution from here: https://stackoverflow.com/a/8963618/1478624
        """

        # make 'daemon' attribute always return False
        def _get_daemon(self):
            return False

        def _set_daemon(self, value):
            pass

        daemon = property(_get_daemon, _set_daemon)

    class MyPool(multiprocessing.pool.Pool):
        Process = NoDaemonProcess

    exp_args = get_exp_args(cfgs, root_path, args.runs_no)

    pool = MyPool(args.procs_no)
    pool.map(function, exp_args)


# --------------------------------------------
# Start and detach experiments using nohup

def get_max_procs(args: Args) -> int:
    """Limit the number of processes by either CPU usage or GPU usage"""
    if args.gpus:
        return min(args.procs_no, args.per_gpu * len(args.gpus))
    return args.procs_no


def launch(py_file: str,
           exp_args: Args,
           timestamp: int,
           ppid: int,
           env: Optional[str],
           gpu: Optional[int] = None,
           omp: Optional[int] = 0,
           mkl: Optional[int] = 0) -> PID:

    err_path = os.path.join(exp_args.out_dir, "err")
    out_path = os.path.join(exp_args.out_dir, "out")

    cmd = f" nohup python -u {py_file:s}" +\
          f" --configs-dir {exp_args.cfg_dir:s}" +\
          f" --config-file cfg" +\
          f" --default-config-file cfg" +\
          f" --out-dir {exp_args.out_dir:s}" +\
          f" --timestamp {timestamp:d} --ppid {ppid:d}" +\
          f" 2>{err_path:s} 1>{out_path:s}" +\
          f" & echo $!"

    if mkl and mkl > 0:
        cmd = f"MKL_NUM_THREADS={mkl:d} {cmd:s}"

    if omp and omp > 0:
        cmd = f"OMP_NUM_THREADS={omp:d} {cmd:s}"

    if gpu is not None:
        cmd = f"CUDA_VISIBLE_DEVICES={gpu:d} {cmd:s}"

    if env:
        cmd = f"source activate {env:s}; {cmd:s}"

    print(f"Command to be run:\n{cmd:s}")

    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)
    (out, err) = proc.communicate()
    err = err.decode("utf-8").strip()
    if err:
        print(f"Some error: {clr(err, 'red'):s}.")
    pid = int(out.decode("utf-8").strip())
    print(f"New PID is {pid:d}.")

    return pid


def get_command(pid: PID) -> str:
    result = subprocess.run(f"ps -p {pid:d} -o cmd h",
                            stdout=subprocess.PIPE,
                            shell=True)
    return result.stdout.decode("utf-8").strip()


def still_active(pid: PID, py_file: str) -> bool:
    cmd = get_command(pid)
    # return cmd and (py_file in cmd)  # mypy doesn't like this
    if cmd:
        return py_file in cmd
    return False


def dump_pids(path, pids):
    with open(os.path.join(path, "active_pids"), "w") as file_handler:
        for pid in pids:
            file_handler.write(f"{pid:d}\n")


def run_from_system(root_path: str, timestamp: int,
                    cfgs: List[Args], args: Args) -> None:
    active_procs: List[Tuple[PID, Optional[int]]] = []
    max_procs_no = get_max_procs(args)
    crt_pid = os.getpid()
    print(f"PID of current process is {crt_pid:d}.")
    print("The maximum number of experiments in parallel will be: ",
          max_procs_no)

    gpus = args.gpus
    epg = args.per_gpu
    py_file = args.module
    py_file = py_file if py_file.endswith(".py") else py_file + ".py"
    assert os.path.isfile(py_file)

    exp_args = get_exp_args(cfgs, root_path, args.runs_no)
    env = value_of(args, "env", None)

    while exp_args:
        if len(active_procs) < max_procs_no:
            gpu = None
            for gpu_j in gpus:
                if len([_ for (_, _g) in active_procs if _g == gpu_j]) < epg:
                    gpu = gpu_j
                    break
            next_args = exp_args.pop()
            new_pid = launch(py_file, next_args, timestamp, crt_pid,
                             env, gpu=gpu, omp=args.omp, mkl=args.mkl)
            active_procs.append((new_pid, gpu))
            dump_pids(root_path, [pid for (pid, _) in active_procs])
        else:
            time.sleep(1)

        old_active_procs = active_procs
        active_procs = []
        changed = False
        for (pid, gpu) in old_active_procs:
            if still_active(pid, py_file):
                active_procs.append((pid, gpu))
            else:
                changed = True
                print(f"Process {pid:d} seems to be done.")
        if changed:
            dump_pids(root_path, [pid for (pid, _) in active_procs])

    wait_time = 1
    while active_procs:
        time.sleep(wait_time)
        wait_time = min(wait_time + 1, 30)
        old_active_procs, active_procs, changed = active_procs, [], False
        for (pid, gpu) in old_active_procs:
            if still_active(pid, py_file):
                active_procs.append((pid, gpu))
            else:
                changed = True
                wait_time = 1
                print(f"Process {pid:d} seems to be done.")
        if changed and active_procs:
            dump_pids(root_path, [pid for (pid, _) in active_procs])
            print("Still active: " +
                  ",".join([str(pid) for (pid, _) in active_procs]) +
                  ". Stop this at any time with no risks.")

    print(clr("All done!", attrs=["bold"]))


def main():
    args = parse_args()
    print(config_to_string(args))

    # Read configuration files

    cfgs = read_config(strict=False)
    cfg0 = cfgs if not isinstance(cfgs, list) else cfgs[0]
    cfgs = [cfgs] if not isinstance(cfgs, list) else cfgs

    root_path: str = None
    timestamp: int
    if args.resume:
        experiment = cfg0.experiment
        previous = [f for f in os.listdir("./results/")
                    if re.match(f"\\d+_{experiment:s}", f)]
        if previous:
            last_time = str(max([int(f.split("_")[0]) for f in previous]))
            print("Resuming", last_time, "!")
            root_path = os.path.join("results",
                                     f"{last_time:s}_{experiment:s}")
            timestamp = int(last_time)
            assert os.path.isdir(root_path)

    if root_path is None:
        timestamp = int(time.time())
        root_path = f"results/{timestamp:d}_{cfg0.experiment:s}/"
        assert not os.path.exists(root_path)
        os.makedirs(root_path)

    if len(cfgs) == 1 and args.runs_no == 1:
        cfg = cfgs[0]
        # If there's a single experiment no subfolders are created

        # Check if results file is already there (experiment is over)
        results_file = os.path.join(root_path, "results.pkl")
        if os.path.isfile(results_file):
            print(f"Skipping {cfgs[0].title:s}. {results_file:s} exists.")
            return

        # Dump config file if there is none
        cfg_file = os.path.join(root_path, "cfg.yaml")
        if not os.path.isfile(cfg_file):
            with open(cfg_file, "w") as yaml_file:
                yaml.safe_dump(namespace_to_dict(cfg), yaml_file,
                               default_flow_style=False)
        cfg.out_dir = root_path
        cfg.run_id = 0
        get_function(args)(cfg)
        return

    if args.no_detach:
        spawn_from_here(root_path, cfgs, args)
    else:
        run_from_system(root_path, timestamp, cfgs, args)


if __name__ == "__main__":
    main()
