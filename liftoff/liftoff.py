""" TODO: write doc
"""

from argparse import Namespace
from functools import partial
from importlib import import_module
import os
import os.path
import subprocess
import sys
import time
import traceback
from typing import Callable, List
from termcolor import colored as clr
import yaml

from .common.dict_utils import dict_to_namespace
from .common.experiment_info import is_experiment, is_yaml
from .common.options_parser import OptionParser


class LiftoffResources:
    """ Here we have a simple class to handle GPU availability.
    """

    def __init__(self, opts):
        self.gpus = opts.gpus
        self.procs_no = opts.procs_no

        if self.gpus:
            if len(opts.gpus) == len(opts.per_gpu):
                self.per_gpu = {
                    g: int(n) for g, n in zip(opts.gpus, opts.per_gpu)
                }
            elif len(opts.per_gpu) == 1:
                self.per_gpu = {g: int(opts.per_gpu[0]) for g in opts.gpus}
            else:
                raise ValueError("Strage per_gpu values. {opts.per_gpu}")
        else:
            self.per_gpu = None

        if self.gpus:
            self.gpu_running_procs = {g: 0 for g in self.gpus}
        self.running_procs = 0

    def process_commands(self, commands: List[str]):
        """ Here we process some commands we got from god knows where that
            might change the way we want to allocate resources.
        """

    def free(self, gpu=None):
        """ Here we inform that some process ended, maybe on a specific gpu.
        """
        if self.gpus:
            self.gpu_running_procs[gpu] -= 1
        self.running_procs -= 1

    def is_free(self) -> tuple:
        """ Here we ask if there are resources available.
        """
        if self.running_procs >= self.procs_no:
            return (False, None)
        if self.gpus:
            for gpu in self.gpus:
                if self.gpu_running_procs[gpu] < self.per_gpu[gpu]:
                    return (True, gpu)
            return (False, None)
        return (True, None)

    def allocate(self, gpu=None) -> None:
        """ Here we allocate resources for some process. Be careful, no checks
            are being performed here. We just increment counters.
        """
        if self.gpus:
            self.gpu_running_procs[gpu] += 1
        self.running_procs += 1


def some_run_path(experiment_path):
    """ So we have that experiment path and we ask for a single subexperiment
        we might run now.
    """

    with os.scandir(experiment_path) as fit:
        for entry in fit:
            if not entry.name.startswith(".") and entry.is_dir():
                subexp_path = os.path.join(experiment_path, entry.name)
                with os.scandir(subexp_path) as fit2:
                    for entry2 in fit2:
                        if not entry2.name.startswith(".") and entry2.is_dir():
                            run_path = os.path.join(subexp_path, entry2.name)
                            cfg_path = os.path.join(run_path, "cfg.yaml")
                            crash_path = os.path.join(run_path, ".__crash")
                            end_path = os.path.join(run_path, ".__end")
                            leaf_path = os.path.join(run_path, ".__leaf")
                            lock_path = os.path.join(run_path, ".__lock")
                            must_be = [cfg_path, leaf_path]
                            must_not_be = [crash_path, end_path, lock_path]

                            if any(not os.path.exists(f) for f in must_be):
                                continue

                            if any(os.path.exists(f) for f in must_not_be):
                                continue

                            return run_path
    return None


def should_stop(experiment_path):
    return os.path.exists(os.paht.join(experiment_path, ".STOP"))


def parse_options() -> Namespace:
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser(
        "liftoff",
        [
            "script",
            "config_path",
            "procs_no",
            "gpus",
            "per_gpu",
            "verbose",
            "copy_to_clipboard",
        ],
    )
    return opt_parser.parse_args()


def get_command_for_pid(pid: int) -> str:
    """ Returns the command for a pid if that process exists.
    """
    result = subprocess.run(
        f"ps -p {pid:d} -o cmd h", stdout=subprocess.PIPE, shell=True
    )
    return result.stdout.decode("utf-8").strip()


def still_active(pid: int, cmd: str) -> bool:
    """ Checks if a subprocess is still active.
    """
    os_cmd = get_command_for_pid(pid)
    return cmd in os_cmd


def lock_file(lock_path: str, session_id: str) -> bool:
    """ Creates a file if it does not exist.
    """
    try:
        lck_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lck_fd, session_id.encode())
        os.close(lck_fd)
        return True
    except FileExistsError:
        return False


def launch_run(run_path, py_script, session_id, gpu=None):
    err_path = os.path.join(run_path, "err")
    out_path = os.path.join(run_path, "out")
    nohup_err_path = os.path.join(run_path, "nohup.err")
    nohup_out_path = os.path.join(run_path, "nohup.out")
    cfg_path = os.path.join(run_path, "cfg.yaml")
    start_path = os.path.join(run_path, ".__start")
    end_path = os.path.join(run_path, ".__end")
    crash_path = os.path.join(run_path, ".__crash")
    env_vars = ""

    with open(cfg_path) as handler:
        title = yaml.load(handler, Loader=yaml.SafeLoader)["title"]

    if gpu is not None:
        env_vars = f"CUDA_VISIBLE_DEVICES={gpu} {env_vars:s}"

    py_cmd = f"python -u {py_script:s} {cfg_path:s} --session-id {session_id}"

    cmd = (
        f" date +%s 1> {start_path:s} 2>/dev/null &&"
        + f" nohup sh -c '{env_vars:s} {py_cmd:s}"
        + f" 2>{err_path:s} 1>{out_path:s}"
        + f" && date +%s > {end_path:s}"
        + f" || date +%s > {crash_path:s}'"
        + f" 1> {nohup_out_path} 2> {nohup_err_path}"
        + f" & echo $!"
    )

    print(f"Command to be run:\n{cmd:s}")

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    (out, err) = proc.communicate()
    err = err.decode("utf-8").strip()
    if err:
        print(f"Some error: {clr(err, 'red'):s}.")
    pid = int(out.decode("utf-8").strip())
    print(f"New PID is {pid:d}.")

    return pid, gpu, title, py_cmd


def launch_experiment(opts):
    resources = LiftoffResources(opts)
    active_pids = []
    pid_path = os.path.join(opts.experiment_path, f".__{opts.session_id}")
    with open(pid_path, "a") as handler:
        handler.write(f"{os.getpid():d}\n")
    while True:
        available, next_gpu = resources.is_free()
        while not available:
            still_active_pids = []
            do_sleep = True
            for info in active_pids:
                pid, gpu, title, cmd, lock_path = info
                if still_active(pid, cmd):
                    still_active_pids.append(info)
                else:
                    print(f"> {title} seems to be over.")
                    os.remove(lock_path)
                    resources.free(gpu=gpu)
                    do_sleep = False
            active_pids = still_active_pids
            if do_sleep:
                time.sleep(1)
            available, next_gpu = resources.is_free()

        if should_stop(opts.experiment_path):
            print("We'll exit once running procs are over.")
            break

        run_path = some_run_path(opts.experiment_path)

        if run_path is None:
            print("Nothing more to run here.")
            break

        lock_path = os.path.join(run_path, ".__lock")

        if lock_file(lock_path, opts.session_id):
            info = launch_run(
                run_path, opts.script, opts.session_id, gpu=next_gpu
            )
            active_pids.append(info + (lock_path,))
            resources.allocate(gpu=next_gpu)

    while active_pids:
        still_active_pids = []
        do_sleep = True
        for info in active_pids:
            pid, gpu, title, cmd, lock_path = info
            if still_active(pid, cmd):
                still_active_pids.append(info)
            else:
                print(f"> {title} seems to be over.")
                os.remove(lock_path)
                resources.free(gpu=gpu)
                do_sleep = False
        active_pids = still_active_pids
        if do_sleep:
            time.sleep(1)

    print(clr(f"Experiment {opts.experiment_path} ended.", attrs=["bold"]))
    os.remove(pid_path)


def systime_to(timestamp_file_path: str) -> None:
    """ Write current system time to a file.
    """
    cmd = f"date +%s 1> {timestamp_file_path:s}"
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
    (_, err) = proc.communicate()
    return err.decode("utf-8").strip()


def wrapper(function: Callable[[Namespace], None], args: Namespace) -> None:
    """ Wrapper around function to be called that also writes info files.
    """
    start_path = os.path.join(args.out_dir, ".__start")
    end_path = os.path.join(args.out_dir, ".__end")
    crash_path = os.path.join(args.out_dir, ".__crash")
    lock_path = os.path.join(args.out_dir, ".__lock")

    if lock_file(lock_path, ""):
        try:
            systime_to(start_path)
            function(args)
            systime_to(end_path)
        except Exception:  # pylint: disable=broad-except
            traceback.print_exc(file=sys.stderr)
            systime_to(crash_path)
        finally:
            os.remove(lock_path)


def get_function(opts: Namespace) -> Callable[[Namespace], None]:
    """ Loads the script and calls run(opts)
    """
    sys.path.append(os.getcwd())
    module_name = opts.script
    if module_name.endswith(".py"):
        module_name = module_name[:-3]
        function = "run"
    else:
        module_name, function = module_name.split(".")

    module = import_module(module_name)
    if function not in module.__dict__:
        raise Exception(f"Module must have function {function}(args).")
    return partial(wrapper, module.__dict__[function])


def run_here(opts):
    from .prepare import parse_options as prepare_parse_options
    from .prepare import prepare_experiment

    prep_args = [opts.config_path, "--do"]
    if opts.copy_to_clipboard:
        prep_args.append("--cc")
    prepare_opts = prepare_parse_options(prep_args)
    opts.experiment_path = prepare_experiment(prepare_opts)

    with os.scandir(opts.experiment_path) as fit:
        for entry in fit:
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            with os.scandir(entry.path) as fit2:
                for entry2 in fit2:
                    if entry2.name.startswith(".") or not entry2.is_dir():
                        continue
                    run_path = entry2.path
                    leaf_path = os.path.join(run_path, ".__leaf")
                    cfg_path = os.path.join(run_path, "cfg.yaml")
                    if os.path.isfile(leaf_path):
                        with open(cfg_path) as handler:
                            cfg = yaml.load(handler, Loader=yaml.SafeLoader)
                        args = dict_to_namespace(cfg)
                        print(clr("\nStarting\n", attrs=["bold"]))
                        get_function(opts)(args)


def launch() -> None:
    """ Main function.
    """
    opts = parse_options()

    if is_experiment(opts.config_path):
        opts.experiment_path = opts.config_path
        launch_experiment(opts)
    elif is_yaml(opts.config_path):
        if opts.gpus:
            raise ValueError("Cannot specify GPU when launching a single run.")
        run_here(opts)
    else:
        raise NotImplementedError

