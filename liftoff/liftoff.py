from argparse import ArgumentParser, Namespace
from typing import Callable, List, Optional
from copy import deepcopy
import sys
import os
from functools import partial
from importlib import import_module
import multiprocessing
import multiprocessing.pool
import time
import traceback
import subprocess
import yaml
from termcolor import colored as clr
from numpy.random import shuffle

from .common.argparsers import add_experiment_args, add_launch_args
from .common.lookup import create_new_experiment_folder, get_latest_experiment
from .common.liftoff_config import get_liftoff_config, save_local_options
from .common.miscellaneous import ask_user_yn
from .common.sys_interaction import systime_to

from .config import read_config, namespace_to_dict, config_to_string


def parse_args() -> Namespace:
    """If you need GPU magic, please use detached processes."""
    # TODO: clean all the fucked up arguments below
    arg_parser = ArgumentParser()
    add_launch_args(arg_parser)
    add_experiment_args(arg_parser)
    return arg_parser.parse_args()


def get_exp_args(cfgs: List[Namespace], root_path: str,
                 runs_no: int) -> List[Namespace]:
    """Takes the configs read from files and augments them with
    out_dir, and run_id"""

    exp_args = []
    for j, cfg in enumerate(cfgs):
        title = cfg.title
        for char in " -.,=:;/()[]'+":
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
                    end_file = os.path.join(exp_path, ".__end")
                    if os.path.isfile(end_file):
                        print(f"Skipping {cfg.title:s} <{run_id:d}>. "
                              f"{end_file:s} exists.")
                        continue
                else:
                    os.makedirs(exp_path)
                crash_file = os.path.join(exp_path, ".__crash")
                if os.path.isfile(crash_file):
                    os.remove(crash_file)
                new_cfg = deepcopy(cfg)
                new_cfg.run_id = run_id
                new_cfg.out_dir = exp_path
                new_cfg.cfg_dir = exp_path
                exp_args.append(new_cfg)
                open(os.path.join(exp_path, ".__leaf"), "a").close()
                cfg_file = os.path.join(exp_path, "cfg.yaml")
                with open(cfg_file, "w") as yaml_file:
                    yaml.safe_dump(namespace_to_dict(new_cfg), yaml_file,
                                   default_flow_style=False)

        else:
            # if there's a single run, no individual folders are created
            end_file = os.path.join(alg_path, ".__end")
            if os.path.isfile(end_file):
                print(f"Skipping {cfg.title:s}. {end_file:s} exists.")
            else:
                crash_file = os.path.join(alg_path, ".__crash")
                if os.path.isfile(crash_file):
                    os.remove(crash_file)
                new_cfg = deepcopy(cfg)
                new_cfg.run_id = 0
                new_cfg.out_dir = alg_path
                new_cfg.cfg_dir = alg_path
                exp_args.append(new_cfg)
                open(os.path.join(alg_path, ".__leaf"), "a").close()
                cfg_file = os.path.join(alg_path, "cfg.yaml")
                with open(cfg_file, "w") as yaml_file:
                    yaml.safe_dump(namespace_to_dict(cfg), yaml_file,
                                   default_flow_style=False)
    shuffle(exp_args)
    return exp_args


# --------------------------------------------
# Run experiments as locally spawned processes


def wrapper(function: Callable[[Namespace], None], args: Namespace) -> None:
    start_file = os.path.join(args.out_dir, ".__start")
    end_file = os.path.join(args.out_dir, ".__end")
    crash_file = os.path.join(args.out_dir, ".__crash")

    try:
        systime_to(start_file)
        function(args)
        systime_to(end_file)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        systime_to(crash_file)


def get_function(args: Namespace) -> Callable[[Namespace], None]:
    sys.path.append(os.getcwd())
    module_name = args.module
    if module_name.endswith(".py"):
        module_name = module_name[:-3]
        function = "run"
    else:
        module_name, function = module_name.split(".")

    module = import_module(module_name)
    if function not in module.__dict__:
        raise Exception(f"Module must have function {function}(args).")
    return partial(wrapper, module.__dict__[function])


def spawn_from_here(root_path: str, cfgs: List[Namespace], args: Namespace):

    # Figure out what should be executed
    function = get_function(args)

    if args.gpus:
        raise Exception("Cannot specify GPUs unless you detach processes")

    if args.procs_no < 1:
        raise Exception(f"Strange number of procs: {args.procs_no:d}")

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

def get_max_procs(args: Namespace) -> int:
    """Limit the number of processes by either CPU usage or GPU usage"""
    if args.gpus:
        return min(args.procs_no, args.per_gpu * len(args.gpus))
    return args.procs_no


def launch(py_file: str,
           exp_args: Namespace,
           timestamp: str,
           ppid: int,
           root_path: str,
           gpu: Optional[int] = None) -> int:

    err_path = os.path.join(exp_args.out_dir, "err")
    out_path = os.path.join(exp_args.out_dir, "out")

    start_path = os.path.join(exp_args.out_dir, '.__start')
    end_path = os.path.join(exp_args.out_dir, '.__end')
    crash_path = os.path.join(exp_args.out_dir, '.__crash')

    env_vars = ""

    if gpu is not None:
        env_vars = f"CUDA_VISIBLE_DEVICES={gpu:d} {env_vars:s}"

    cmd = f" date +%s 1> {start_path:s} 2>/dev/null &&" +\
          f" nohup sh -c '{env_vars:s} python -u {py_file:s}" +\
          f" --configs-dir {exp_args.cfg_dir:s}" +\
          f" --config-file cfg" +\
          f" --default-config-file cfg" +\
          f" --out-dir {exp_args.out_dir:s}" +\
          f" --id {timestamp:s}_{ppid:d}" +\
          f" 2>{err_path:s} 1>{out_path:s}" +\
          f" && date +%s > {end_path:s}" +\
          f" || date +%s > {crash_path:s}'" +\
          f" 1> {os.path.join(root_path, 'nohup_out')}" +\
          f" 2> {os.path.join(root_path, 'nohup_err')}" +\
          f" & echo $!"
    # f" & ps --ppid $! -o pid h"

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


def get_command(pid: int) -> str:
    result = subprocess.run(f"ps -p {pid:d} -o cmd h",
                            stdout=subprocess.PIPE,
                            shell=True)
    return result.stdout.decode("utf-8").strip()


def still_active(pid: int, py_file: str) -> bool:
    cmd = get_command(pid)
    # return cmd and (py_file in cmd)  # mypy doesn't like this
    if cmd:
        return py_file in cmd
    return False


def dump_pids(path, pids):
    with open(os.path.join(path, "active_pids"), "w") as file_handler:
        for pid in pids:
            file_handler.write(f"{pid:d}\n")


def run_from_system(root_path: str, timestamp: str,
                    cfgs: List[Namespace], args: Namespace) -> None:
    active_procs = []  # type: : List[Tuple[int, Optional[int]]]
    max_procs_no = get_max_procs(args)
    crt_pid = os.getpid()
    print(f"PID of current process is {crt_pid:d}.")
    print("The maximum number of experiments in parallel will be: ",
          max_procs_no)

    gpus = args.gpus
    epg = args.per_gpu
    py_file = args.module
    py_file = py_file if py_file.endswith(".py") else py_file + ".py"
    if not os.path.isfile(py_file):
        raise FileNotFoundError("Could not find {py_file:s}.")

    exp_args = get_exp_args(cfgs, root_path, args.runs_no)

    while exp_args:
        if len(active_procs) < max_procs_no:
            gpu = None
            for gpu_j in gpus:
                if len([_ for (_, _g) in active_procs if _g == gpu_j]) < epg:
                    gpu = gpu_j
                    break
            next_args = exp_args.pop()
            new_pid = launch(py_file, next_args, timestamp, crt_pid, root_path,
                             gpu=gpu)
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


def args_from_liftoff_config(args: Namespace) -> None:
    lft_cfg = get_liftoff_config()
    no_questions = lft_cfg is not None and lft_cfg.get("no_questions", False)

    if args.module is None:
        if lft_cfg is not None and "module" in lft_cfg:
            args.module = lft_cfg["module"]
        else:
            raise RuntimeError("You did not provide a script to be run.")
    elif not no_questions and (lft_cfg is None or "module" not in lft_cfg):
        flag_name = "asked_about_module"
        asked = False
        if lft_cfg is not None:
            asked = lft_cfg.get("history", {}).get(flag_name, False)
        if not asked:
            question = f"Do you want to save {args.module:s} as the " + \
                "default script for this project?"
            new_options = {"history": {flag_name: True}}
            try:
                if ask_user_yn(question):
                    new_options["module"] = args.module
            except OSError:
                return
            save_local_options(new_options)


def create_symlink(experiment_path: str):
    src = os.path.normpath(experiment_path)
    dst = os.path.join(os.path.dirname(src), "latest")
    #src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if os.path.islink(dst):
        os.unlink(dst)
    os.symlink(os.path.basename(src), dst)


def main():
    args = parse_args()

    args_from_liftoff_config(args)

    print(config_to_string(args))

    # Read configuration files

    cfgs = read_config(strict=False)
    cfg0 = cfgs if not isinstance(cfgs, list) else cfgs[0]
    cfgs = [cfgs] if not isinstance(cfgs, list) else cfgs

    if args.resume:
        # -------------------- RESUMING A PREVIOUS EXPERIMENT -----------------
        full_name, experiment_path = get_latest_experiment(cfg0.experiment,
                                                           args.timestamp,
                                                           args.timestamp_fmt,
                                                           args.results_dir)
    else:
        # -------------------- STARTING A NEW EXPERIMENT --------------------
        full_name, experiment_path = create_new_experiment_folder(
            cfg0.experiment, args.timestamp_fmt, args.results_dir)

    create_symlink(experiment_path)

    timestamp, *_other = full_name.split("_")

    with open(os.path.join(experiment_path, ".__ppid"), "w") as ppid_file:
        ppid_file.write(f"{os.getpid():d}\n")
    if args.comment:
        with open(os.path.join(experiment_path, ".__comment"), "w") as c_file:
            c_file.write(args.comment)

    if len(cfgs) == 1 and args.runs_no == 1:
        with open(os.path.join(experiment_path, ".__mode"), "w") as m_file:
            m_file.write("single\n")

        cfg = cfgs[0]

        # Check if .__end file is already there (experiment is over)
        end_file = os.path.join(experiment_path, ".__end")
        if os.path.isfile(end_file):
            print(f"Skipping {cfgs[0].title:s}. {end_file:s} exists.")
            return

        crash_file = os.path.join(experiment_path, ".__crash")
        if os.path.isfile(crash_file):
            os.remove(crash_file)

        # Dump config file if there is none
        cfg_file = os.path.join(experiment_path, "cfg.yaml")
        if not os.path.isfile(cfg_file):
            with open(cfg_file, "w") as yaml_file:
                yaml.safe_dump(namespace_to_dict(cfg), yaml_file,
                               default_flow_style=False)
        open(os.path.join(experiment_path, ".__leaf"), "a").close()
        cfg.out_dir, cfg.run_id = experiment_path, 0
        get_function(args)(cfg)
    elif args.no_detach:
        with open(os.path.join(experiment_path, ".__mode"), "w") as m_file:
            m_file.write("multiprocess\n")
        spawn_from_here(experiment_path, cfgs, args)
    else:
        with open(os.path.join(experiment_path, ".__mode"), "w") as m_file:
            m_file.write("nohup\n")
        run_from_system(experiment_path, timestamp, cfgs, args)


if __name__ == "__main__":
    main()
