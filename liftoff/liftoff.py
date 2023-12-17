""" TODO: write doc
"""

import os
import os.path
import random
import subprocess
import sys
import time
import traceback
import psutil
import platform
import threading
from argparse import Namespace
from functools import partial
from importlib import import_module
from time import perf_counter
from typing import Callable, List

import yaml
from termcolor import colored as clr

from .common.dict_utils import dict_to_namespace
from .common.experiment_info import is_experiment, is_yaml, experiment_matches
from .common.options_parser import OptionParser
from .prepare import parse_options as prepare_parse_options
from .prepare import prepare_experiment


class LiftoffResources:
    """Here we have a simple class to handle GPU availability."""

    def __init__(self, opts):
        self.gpus = opts.gpus
        self.procs_no = opts.procs_no

        # Used in windows implementation
        self.pid_dict = {}
        self.pid_events = {}

        if self.gpus:
            if len(opts.gpus) == len(opts.per_gpu):
                self.per_gpu = {g: int(n) for g, n in zip(opts.gpus, opts.per_gpu)}
            elif len(opts.per_gpu) == 1:
                self.per_gpu = {g: int(opts.per_gpu[0]) for g in opts.gpus}
            else:
                raise ValueError(f"Strange per_gpu values. {opts.per_gpu}")
        else:
            self.per_gpu = None

        if self.gpus:
            self.gpu_running_procs = {g: 0 for g in self.gpus}
        self.running_procs = 0

    def process_commands(self, commands: List[str]):
        """Here we process some commands we got from god knows where that
        might change the way we want to allocate resources.
        """
        pass

    def free(self, gpu=None):
        """Here we inform that some process ended, maybe on a specific gpu."""
        if self.gpus:
            self.gpu_running_procs[gpu] -= 1
        self.running_procs -= 1

    def is_free(self) -> tuple:
        """Here we ask if there are resources available."""
        if self.running_procs >= self.procs_no:
            return (False, None)
        if self.gpus:
            for gpu in self.gpus:
                if self.gpu_running_procs[gpu] < self.per_gpu[gpu]:
                    return (True, gpu)
            return (False, None)
        return (True, None)

    def allocate(self, gpu=None) -> None:
        """Here we allocate resources for some process. Be careful, no checks
        are being performed here. We just increment counters.
        """
        if self.gpus:
            self.gpu_running_procs[gpu] += 1
        self.running_procs += 1

    @property
    def state(self):
        """Returns the state of the computing resources."""
        msg = f"Procs: {self.running_procs} / {self.procs_no}"
        if self.gpus:
            msg += f" | {len(self.gpus):d} GPUS:"
            for gpu in self.gpus:
                msg += f" {gpu}:{self.gpu_running_procs[gpu]}/{self.per_gpu[gpu]};"
        return msg


def some_run_path(experiment_path, filters=None):
    """So we have that experiment path and we ask for a single subexperiment
    we might run now.
    """
    must_be = ["cfg.yaml", ".__leaf"]
    must_not_be = [".__lock", ".__crash", ".__end", ".__start"]
    with os.scandir(experiment_path) as fit:
        for entry in fit:
            if not entry.name.startswith(".") and entry.is_dir():
                subexp_path = os.path.join(experiment_path, entry.name)
                with os.scandir(subexp_path) as fit2:
                    for entry2 in fit2:
                        if not entry2.name.startswith(".") and entry2.is_dir():
                            run_path = os.path.join(subexp_path, entry2.name)
                            done_before = False
                            mandatory_files = []
                            with os.scandir(run_path) as fit3:
                                for entry3 in fit3:
                                    if entry3.name in must_not_be:
                                        done_before = True
                                        break
                                    if entry3.name in must_be:
                                        mandatory_files.append(entry3.name)
                            if done_before or set(mandatory_files) != set(must_be):
                                continue
                            if filters and not experiment_matches(run_path, filters):
                                print(f"Skipping {run_path:s} as it was filtered out.")
                                continue
                            yield run_path


def should_stop(experiment_path):
    """Checks if liftoff should exit no mather how much is left to run."""
    return os.path.exists(os.path.join(experiment_path, ".STOP"))


def parse_options() -> Namespace:
    """Parse command line arguments and liftoff configuration."""

    opt_parser = OptionParser(
        "liftoff",
        [
            "script",
            "config_path",
            "procs_no",
            "gpus",
            "per_gpu",
            "no_detach",
            "verbose",
            "copy_to_clipboard",
            "time_limit",  # This should be removed in favour of start_by
            "start_by",
            "end_by",
            "optimize",
            "args",
            "filters",
            "results_path",
            "name",
            "max_runs",
            "shuffle",
        ],
    )
    return opt_parser.parse_args()


def get_command_for_pid(pid: int) -> str:
    """Returns the command for a pid if that process exists."""
    try:
        process = psutil.Process(pid)
        return " ".join(process.cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        # Process does not exist or access is denied
        return ""


def still_active(pid: int, cmd) -> bool:
    """Checks if a subprocess is still active."""
    if isinstance(cmd, list):
        cmd = " ".join(cmd)  # Convert list to string

    os_cmd = get_command_for_pid(pid)
    return cmd in os_cmd


def lock_file(lock_path: str, session_id: str) -> bool:
    """Creates a file if it does not exist."""
    try:
        lck_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lck_fd, session_id.encode())
        os.close(lck_fd)
        return True
    except FileExistsError:
        return False
    except BlockingIOError:
        sys.stderr.write(f"Some problem while locking {lock_path}!\n")

    return False


def launch_run(  # pylint: disable=bad-continuation
    run_path,
    py_script,
    session_id,
    gpu=None,
    do_nohup=True,
    optim=False,
    end_by=None,
    resources=None,
):
    """Here we launch a run from an experiment.
    This might be the most important function here.
    """
    # Common path setup
    err_path = os.path.join(run_path, "err")
    out_path = os.path.join(run_path, "out")
    cfg_path = os.path.join(run_path, "cfg.yaml")
    start_path = os.path.join(run_path, ".__start")
    end_path = os.path.join(run_path, ".__end")
    crash_path = os.path.join(run_path, ".__crash")

    flags = "-u -OO" if optim else "-u"
    
    with open(cfg_path) as handler:
        title = yaml.load(handler, Loader=yaml.SafeLoader)["title"]

    # Determine the platform
    platform_is_windows = platform.system() == "Windows"

    # Unix-specific command setup
    if platform_is_windows:
        env_vars = os.environ.copy()
        
        if gpu is not None:
            env_vars["CUDA_VISIBLE_DEVICES"] = str(gpu)
        if end_by is not None:
            env_vars["ENDBY"] = str(end_by)
            
        py_cmd = (
            [sys.executable, flags]
            + py_script.split()
            + [cfg_path, "--session-id", session_id]
        )

        # Write the start time
        with open(start_path, "w") as f:
            f.write(str(int(time.time())))

        experiment_id = f"({title}):({int(time.time())})"
        resources.pid_events[experiment_id] = threading.Event()

        # Function to execute the subprocess
        def run_experiment(exp_id):
            with open(err_path, "w") as err_file, open(out_path, "w") as out_file:
                proc = subprocess.Popen(
                    py_cmd, stdout=out_file, stderr=err_file, env=env_vars
                )

                # Store the PID and signal main branch can continue
                resources.pid_dict[exp_id] = proc.pid
                resources.pid_events[exp_id].set()

                # Wait for the process to complete
                proc.wait()

                # Check if the process terminated unexpectedly
                if proc.returncode != 0:
                    with open(crash_path, "w") as f:
                        f.write(str(int(time.time())))
                    print(
                        f"Process {proc.pid} terminated unexpectedly with return code {proc.returncode}"
                    )
                else:
                    # Write to the end file if the process completes successfully
                    with open(end_path, "w") as f:
                        f.write(str(int(time.time())))

        # Launch the subprocess in a separate thread
        experiment_thread = threading.Thread(
            target=run_experiment, args=(experiment_id,)
        )
        experiment_thread.start()

        # Wait for the PID to be available and store it
        resources.pid_events[experiment_id].wait()
        pid = resources.pid_dict[experiment_id]

    else:
        wrap_err_path = os.path.join(run_path, "nohup.err" if do_nohup else "sh.err")
        wrap_out_path = os.path.join(run_path, "nohup.out" if do_nohup else "sh.out")
        env_vars = ""

        if gpu is not None:
            env_vars = f"CUDA_VISIBLE_DEVICES={gpu} {env_vars:s}"
        if end_by is not None:
            env_vars += f" ENDBY={end_by}"
            
        py_cmd = f"python {flags} {py_script:s} {cfg_path:s} --session-id {session_id}"
        
         # Common command prefix and suffix
        cmd_prefix = f" date +%s 1> {start_path:s} 2>/dev/null &&"
        cmd_suffix = f" 2>{err_path:s} 1>{out_path:s} && date +%s > {end_path:s}" \
                    f" || date +%s > {crash_path:s} 1> {wrap_out_path} 2> {wrap_err_path}"

        # Main command
        main_cmd = f"'{env_vars:s} {py_cmd:s}"

        # Construct the full command based on 'do_nohup'
        if do_nohup:
            cmd = f"{cmd_prefix} nohup sh -c {main_cmd} {cmd_suffix} & echo $!"
        else:
            cmd = f"{cmd_prefix} sh -c {main_cmd} {cmd_suffix} & echo $!"

        print(f"[{time.strftime(time.ctime())}] Command to be run:\n{cmd:s}")
        sys.stdout.flush()
    
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        (out, err) = proc.communicate()
        if err:
            print(f"[{time.strftime(time.ctime())}] Some error: {clr(err, 'red'):s}.")
        pid = int(out.decode("utf-8").strip())

    print(f"[{time.strftime(time.ctime())}] New PID is {pid}.")
    sys.stdout.flush()
    return pid, gpu, title, py_cmd


def refresh_pids(active_pids, resources):
    """This function gets the previous list of running processes, the resources, and
    return the new list of pids. The resources are modified if some processes ended.
    """
    still_active_pids = []
    no_change = True
    for info in active_pids:
        pid, gpu, title, cmd, lock_path = info
        if still_active(pid, cmd):
            still_active_pids.append(info)
        else:
            print(f"[{time.strftime(time.ctime())}] {title} seems to be over.")
            os.remove(lock_path)
            resources.free(gpu=gpu)
            no_change = False
    return still_active_pids, no_change


def shuffle(some_generator):
    """Takes a generator and returns a shuffled generator."""
    seq = list(some_generator)
    random.shuffle(seq)
    for x in seq:
        yield x


def launch_experiment(opts):
    """This is like the most important function in the whole Universe."""
    resources = LiftoffResources(opts)
    active_pids = []
    pid_path = os.path.join(opts.experiment_path, f".__{opts.session_id}")

    start = perf_counter()
    run_cnt = 0
    sleep_time = 1
    launched_something = False

    with open(pid_path, "a") as handler:
        handler.write(f"{os.getpid():d}\n")
    while True:
        print(f"[{time.strftime(time.ctime())}] Resources:", resources.state)
        if not launched_something:
            active_pids, _ = refresh_pids(active_pids, resources)

        available, next_gpu = resources.is_free()
        print(f"[{time.strftime(time.ctime())}] Free??: {available}, {next_gpu}")
        while not available:
            active_pids, do_sleep = refresh_pids(active_pids, resources)
            if do_sleep:
                time.sleep(sleep_time)
            available, next_gpu = resources.is_free()

        # There are several conditions that stop liftoff:
        # 1. someone created the .STOP file in that experiment
        # 2. start_by has been exceeded
        # 3. end_by has been exceeded   (if start_by has not beed provided)
        # 4. max-runs has been exceeded

        if should_stop(opts.experiment_path):
            print(f"[{time.strftime(time.ctime())}] Exit once running procs are over.")
            break

        if opts.start_by > 0 and (perf_counter() - start) > opts.start_by:
            print(
                f"[{time.strftime(time.ctime())}] Cannot launch more processes."
                " Time limit exceeded."
            )
            break

        if opts.end_by > 0 and (perf_counter() - start) > opts.end_by:
            print(
                f"[{time.strftime(time.ctime())}] Cannot launch more processes."
                " Time limit exceeded."
            )
            break

        if opts.max_runs > 0 and opts.max_runs <= run_cnt:
            print(
                f"[{time.strftime(time.ctime())}] Max runs exceeded. {opts.max_runs} "
            )
            break

        run_paths = some_run_path(opts.experiment_path, filters=opts.filters)
        if opts.shuffle:
            run_paths = shuffle(run_paths)

        path_start = perf_counter()
        attempt = 0
        launched_something = False
        for run_path in run_paths:
            attempt += 1
            lock_path = os.path.join(run_path, ".__lock")
            if lock_file(lock_path, opts.session_id):
                path_delta = perf_counter() - path_start
                print(
                    f"[{time.strftime(time.ctime())}] Path search took "
                    f"{path_delta:.3f} s. ({attempt:d} attempts)"
                )
                launched_something = True
                if opts.end_by > 0:
                    end_by = int(opts.end_by - (perf_counter() - start))
                else:
                    end_by = None
                info = launch_run(
                    run_path,
                    opts.script,
                    opts.session_id,
                    gpu=next_gpu,
                    do_nohup=not opts.no_detach,
                    optim=opts.optimize,
                    end_by=end_by,
                    resources=resources,
                )
                active_pids.append(info + (lock_path,))
                resources.allocate(gpu=next_gpu)
                break
        if not launched_something:
            print(
                f"[{time.strftime(time.ctime())}] "
                "All subexperiments are done / running."
            )
            if not active_pids:
                break
            sleep_time = min(16, sleep_time * 2)
            time.sleep(sleep_time)
        else:
            sleep_time = 1

        run_cnt += launched_something

    while active_pids:
        active_pids, do_sleep = refresh_pids(active_pids, resources)
        if do_sleep:
            time.sleep(2)

    duration = perf_counter() - start
    msg = (
        f"[{time.strftime(time.ctime())}] "
        f"Experiment {opts.experiment_path} ended after {duration:.2f}s."
    )
    print(clr(msg, attrs=["bold"]))
    os.remove(pid_path)


def systime_to(timestamp_file_path: str) -> None:
    """Write current system time to a file."""
    with open(timestamp_file_path, "w") as file:
        file.write(str(int(time.time())))


def wrapper(function: Callable[[Namespace], None], args: Namespace) -> None:
    """Wrapper around function to be called that also writes info files."""
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
    """Loads the script and calls run(opts)"""
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
    """If there's a single run in the experiment we run it in this process by
    calling run in the script.
    """
    prep_args = [opts.config_path, "--do"]
    if opts.copy_to_clipboard:
        prep_args.append("--cc")
    prepare_opts = prepare_parse_options(prep_args)
    # prepare_opts.args = opts.args
    prepare_opts.__dict__.update(vars(opts))

    # Fast_check if cfg file is already prepared
    with open(opts.config_path) as handler:
        dummy_config = yaml.load(handler, Loader=yaml.SafeLoader)
    if "out_dir" in dummy_config and os.path.isdir(dummy_config["out_dir"]):
        opts.experiment_path = dummy_config["out_dir"]

        run_path = dummy_config["out_dir"]
        leaf_path = os.path.join(run_path, ".__leaf")
        cfg_path = os.path.join(run_path, "cfg.yaml")
        if os.path.isfile(leaf_path):
            with open(cfg_path) as handler:
                cfg = yaml.load(handler, Loader=yaml.SafeLoader)
            args = dict_to_namespace(cfg)
            print(clr("\nStarting\n", attrs=["bold"]))
            get_function(opts)(args)
    else:
        # Virgin cfg
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


def check_opts_integrity(opts):
    """Here we do some checks..."""
    if opts.args:
        raise ValueError("--args works for single experiment only; see liftoff-prepare")
    if opts.no_detach and opts.procs_no != 1:
        raise ValueError("No detach mode only for single processes")


def launch() -> None:
    """Main function."""
    opts = parse_options()

    if (not os.path.isdir(opts.config_path)) and (not os.path.isfile(opts.config_path)):
        raise FileNotFoundError(f"Cannot find path: {opts.config_path}")

    if is_experiment(opts.config_path):
        opts.experiment_path = opts.config_path
        check_opts_integrity(opts)
        launch_experiment(opts)
    elif is_yaml(opts.config_path):
        if opts.gpus:
            raise ValueError("Cannot specify GPU when launching a single run.")
        run_here(opts)
    else:
        raise NotImplementedError
