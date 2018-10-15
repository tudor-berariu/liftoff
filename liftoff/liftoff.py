# TODO: This needs major refactoring! Version .3 scheduled for this autumn.

from importlib import import_module
from argparse import ArgumentParser, Namespace
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from types import SimpleNamespace
from copy import deepcopy
import hashlib
import sys
import os
from functools import partial
import socket
import selectors
import re
import multiprocessing
import multiprocessing.pool
import time
import traceback
import subprocess
import shutil
import yaml
from termcolor import colored as clr
import numpy as np
from numpy.random import shuffle
from tabulate import tabulate

from .config import read_config, namespace_to_dict, config_to_string,\
    value_of, dict_to_namespace, _update_config as update_config
from .utils.sys_interaction import systime_to
from .version import welcome
from .genetics import get_mutator
from .utils.miscellaneous import ord_dict_to_string

Args = Namespace
PID = int


class LiftoffState:

    def __init__(self, args: Namespace, evolves: bool = True) -> None:
        self.do_quit = False
        self.runs_no = args.runs_no

        self.gpus = args.gpus
        assert isinstance(self.gpus, list)

        self.procs_no = args.procs_no
        assert isinstance(self.procs_no, int)

        self.per_gpu = {g: args.per_gpu for g in args.gpus}

        self._evolves = evolves
        self.selection = "squared_rank"
        # TODO: review default values
        self.crossover = .1
        self.random = .005
        self.momentum = 1 - self.crossover - self.random - .1
        self.refresh_freq = 10
        self.steps = 100
        self.drop_below_zero = True

        self._components = ["gpus", "procs_no", "per_gpu"]

        if evolves:
            self._components.extend(["selection", "crossover", "random",
                                     "momentum", "steps", "refresh_freq",
                                     "drop_below_zero",
                                     "runs_no"])

    @property
    def table(self) -> str:
        all_vars = []
        for var_name in self._components:
            all_vars.append((var_name, getattr(self, var_name)))
        return tabulate(all_vars)

    @property
    def flat(self) -> str:
        all_vars = []
        for var_name in self._components:
            all_vars.append(var_name + "=" + str(getattr(self, var_name)))
        return ";".join(all_vars)

    def process_commands(self, data: SimpleNamespace) -> None:
        # TODO: This must be changed to something more intelligent
        commands = data.inb.split(b' END\n')
        data.inb = commands[-1]
        commands = commands[:-1]
        answers = []

        for command in commands:
            words = [word for word in command.decode().split() if word]
            nwords = len(words)
            if not words:
                answers.append("Empty command.")
            elif words[0] == "quit":
                self.do_quit = True
            elif words[0] not in ["set", "add", "remove"]:
                answers.append("Commands must start with set / add / remove.")
            elif nwords != 3 and not (nwords == 4 and words[1] == "per_gpu"):
                answers.append("Wrong command: " + " ".join(words))
            elif words[0] in ["add", "remove"] and (words[1] != "gpu" or nwords < 2):
                answers.append("Wrong command: " + " ".join(words))
            elif words[0] == "add":
                for new_gpu in words[2:]:
                    if new_gpu in self.gpus:
                        answers.append(f"GPU {new_gpu:s} already in use.")
                    else:
                        self.gpus.append(new_gpu)
                        self.per_gpu[new_gpu] = cnt = min(self.per_gpu.values())
                        answers.append(f"OK. Added gpu {new_gpu:s} waiting for {cnt:d} experiments.")
            elif words[0] == "remove":
                for old_gpu in words[2:]:
                    if old_gpu not in self.gpus:
                        answers.append(f"GPU {old_gpu:s} not in use.")
                    else:
                        self.gpus.remove(old_gpu)
                        del self.per_gpu[old_gpu]
                        answers.append(f"OK. Removed gpu {old_gpu:s}.")
            elif words[1] not in self._components:
                answers.append(f"Unknown field {words[1]:s}.")
            elif words[1] != "per_gpu":
                if words[1] in ["random", "crossover", "momentum"]:
                    func = float
                elif words[1] in ["runs_no", "procs_no", "steps", "refresh_freq"]:
                    func = int
                elif words[1] in ["drop_below_zero"]:
                    def func(x): return bool(int(x))
                else:
                    func = str
                try:
                    setattr(self, words[1], func(words[2]))
                    answers.append(f"Set {words[1]} to {words[2]}.")
                except ValueError as exc:
                    answers.append(str(exc))
            elif nwords == 3:
                try:
                    value = int(words[2])
                    self.per_gpu = {gpu: value for gpu in self.per_gpu.keys()}
                    answers.append(f"Set per_gpu to {value:d} for all gpus.")
                except ValueError as exc:
                    answers.append(str(exc))
            else:
                try:
                    gpu_id = int(words[2])
                    if gpu_id not in self.gpus:
                        answers.append(f"Unknown gpu {gpu_id:d}.")
                    else:
                        value = int(words[3])
                        self.per_gpu[gpu_id] = value
                        answers.append(f"Set per_gpu to {value:d} for gpu {gpu_id:s}.")
                except ValueError as exc:
                    answers.append(str(exc))

        for answer in answers:
            data.outb += (answer + '\n').encode('utf-8')
        data.outb += (self.flat + ' END\n').encode('utf-8')


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
        help="Resume last experiment or that indicated by timestamp.")
    arg_parser.add_argument(
        '--timestamp',
        type=str,
        dest="timestamp",
        help="Timestamp of experiment to resume.")
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
    arg_parser.add_argument(
        "--comment",
        type=str,
        dest="comment",
        default="",
        help="Short comment")
    arg_parser.add_argument(
        '--configs-dir',
        type=str,
        default='./configs',
        dest='configs_dir',
        help='Folder to search for config files.'
    )
    arg_parser.add_argument(
        '-e', '--experiment',
        type=str,
        default="",
        dest="experiment",
        help="Experiment. Overrides cf and dcf"
    )
    return arg_parser.parse_known_args()[0]


def read_fitness(root_path: str,
                 drop_below_zero: bool) -> Tuple[List[str], List[float]]:
    fitnesss, paths = [], []
    nscores = 0
    for rel_path, _dirs, files in os.walk(root_path):
        if not all((f in files) for f in ['.__leaf', 'genotype.yaml', 'fitness']):
            continue
        with open(os.path.join(rel_path, "fitness")) as handler:
            fitness = float(handler.readline().strip())
            if fitness < 0 and drop_below_zero:
                continue
            paths.append(os.path.join(rel_path, 'genotype.yaml'))
            fitnesss.append(fitness)
            nscores += 1
    print(f"[Main] {nscores:d} scores found.")
    return fitnesss, paths


def roulette_probs(scores: np.ndarray) -> np.ndarray:
    if np.any(scores < 0):
        scores = np.exp(scores)
    return scores / np.sum(scores)


def rank_probs(scores: np.ndarray) -> np.ndarray:
    inv_ranks = np.argsort(scores) + 1
    return inv_ranks / np.sum(inv_ranks)


def square_rank_probs(scores: np.ndarray) -> np.ndarray:
    inv_ranks = np.argsort(scores) + 1
    squared_ranks = inv_ranks * inv_ranks
    return squared_ranks / np.sum(squared_ranks)


def read_genotype(path: str) -> Namespace:
    with open(path) as handler:
        cfg = yaml.load(handler, Loader=yaml.SafeLoader)
    return dict_to_namespace(cfg)


def genetic_search(state: LiftoffState,
                   root_path: str, args: Namespace) -> Iterable[Args]:
    path = os.path.join(args.configs_dir, args.experiment)
    default_cfg = read_genotype(os.path.join(path, "default.yaml"))
    genotype_cfg = read_genotype(os.path.join(path, "genotype.yaml"))

    mutator = get_mutator(genotype_cfg)

    # -- TODO: Improve this

    if hasattr(genotype_cfg, "meta"):
        if hasattr(genotype_cfg.meta, "crossover"):
            state.crossover = genotype_cfg.meta.crossover
        if hasattr(genotype_cfg.meta, "momentum"):
            state.momentum = genotype_cfg.meta.momentum
        if hasattr(genotype_cfg.meta, "steps"):
            state.steps = genotype_cfg.meta.steps
        if hasattr(genotype_cfg.meta, "refresh_freq"):
            state.refresh_freq = genotype_cfg.meta.refresh_freq
        if hasattr(genotype_cfg.meta, "selection"):
            state.selection = genotype_cfg.meta.selection
        if hasattr(genotype_cfg.meta, "random"):
            state.random = genotype_cfg.meta.random
        if hasattr(genotype_cfg.meta, "drop_below_zero"):
            state.drop_below_zero = genotype_cfg.meta.drop_below_zero

    print(state.table)

    # ---

    to_run_path = os.path.join(root_path, "to_run")

    to_probs = {'roulette': roulette_probs,
                'rank': rank_probs,
                'squared_rank': square_rank_probs}

    step = 0
    fitnesss, paths = read_fitness(root_path, state.drop_below_zero)
    scores = to_probs[state.selection](np.array(fitnesss))

    while step < state.steps and not state.do_quit:
        print(f"[Main] Step {step:d}.")
        found = False
        while not found:
            manual_path = None
            probe = np.random.sample()
            if os.path.isdir(to_run_path) and [f for f in os.listdir(to_run_path) if f.endswith(".yaml")]:
                for fname in os.listdir(to_run_path):
                    if fname.endswith(".yaml"):
                        try:
                            manual_path = os.path.join(to_run_path, fname)
                            new_genotype = read_genotype(manual_path)
                            new_genotype.meta = Namespace(source="manual")
                            mutator.to_phenotype(new_genotype)  # Just to see it's ok
                            print("Running a manually added file:")
                            break
                        except Exception as exc:
                            os.remove(manual_path)
                            print(str(exc))
                            print(f"\n{fname:s} was deleted\n\n")
                            with open(os.path.join(to_run_path, "log"), "a") as logfile:
                                logfile.write(str(exc))
                                logfile.write(f"\n{fname:s} was deleted\n\n")
            elif scores.size == 0 or probe < state.random:
                print("[Main] Generating random experiment.")
                new_genotype = mutator.sample()
            elif probe < state.crossover + state.random:
                print("[Main] Generating child experiment through crossover.")
                parent1 = read_genotype(np.random.choice(paths, p=scores))
                parent2 = read_genotype(np.random.choice(paths, p=scores))
                new_genotype = mutator.crossover(parent1, parent2)
            else:
                print("[Main] Mutating some experiment.")
                rand_idx = np.random.choice(range(len(scores)), p=scores)
                parent_genotype = read_genotype(paths[rand_idx])
                parent_fitness = fitnesss[rand_idx]
                threshold = state.momentum + state.crossover + state.random
                new_genotype = mutator.mutate(parent_genotype,
                                              parent_fitness=parent_fitness,
                                              follow_momentum=(probe < threshold))

            new_phenotype = mutator.to_phenotype(new_genotype)
            title = ord_dict_to_string(new_genotype.__dict__, ignore=["meta"])
            if len(title) > 200:
                title = hashlib.md5(title.encode('utf-8')).hexdigest()
            title_path = os.path.join(root_path, title)
            if not os.path.isdir(title_path):
                os.makedirs(title_path)
                existing = []
            else:
                existing = os.listdir(title_path)

            for i in range(state.runs_no):
                print("Trying for run", i, "/", state.runs_no)
                may_start = False
                if str(i) not in existing:
                    may_start = True
                else:
                    crash_path = os.path.join(title_path, str(i), ".__crash")
                    if os.path.isfile(crash_path):
                        print("restarting")
                        os.remove(crash_path)
                        may_start = True

                if may_start:
                    experiment_path = os.path.join(title_path, str(i))
                    if not os.path.isdir(experiment_path):
                        os.makedirs(experiment_path)
                    new_cfg = deepcopy(default_cfg)
                    update_config(new_cfg, new_phenotype)
                    new_cfg.run_id = i
                    new_cfg.out_dir = experiment_path
                    new_cfg.cfg_dir = experiment_path

                    # -- Create the new files
                    open(os.path.join(experiment_path, ".__leaf"), "a").close()
                    cfg_path = os.path.join(experiment_path, "cfg.yaml")
                    with open(cfg_path, "w") as yaml_file:
                        yaml.safe_dump(namespace_to_dict(new_cfg), yaml_file,
                                       default_flow_style=False)
                    genotype_path = os.path.join(experiment_path, "genotype.yaml")
                    with open(genotype_path, "w") as yaml_file:
                        yaml.safe_dump(namespace_to_dict(new_genotype), yaml_file,
                                       default_flow_style=False)
                    phenotype_path = os.path.join(experiment_path, "phenotype.yaml")
                    with open(phenotype_path, "w") as yaml_file:
                        yaml.safe_dump(namespace_to_dict(new_phenotype), yaml_file,
                                       default_flow_style=False)

                    yield new_cfg
                    found = True
                    break
            if manual_path and not found:
                # It means a given genotype was already executed runs_no times
                with open(os.path.join(to_run_path, "log"), "a") as logfile:
                    logfile.write(f"{manual_path:s} done\n")
                print(f"{manual_path:s} done\n")
                os.remove(manual_path)
        step += 1

        if step % state.refresh_freq == 0:
            fitnesss, paths = read_fitness(root_path, state.drop_below_zero)
            scores = to_probs[state.selection](np.array(fitnesss))

    print("Genetics are done.")


def get_exp_args(cfgs: List[Args], root_path: str, runs_no: int) -> Iterable[Args]:
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


def wrapper(function: Callable[[Args], None], args: Args) -> None:
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


def get_function(args: Args) -> Callable[[Args], None]:
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


def spawn_from_here(exp_args: Iterable[Args], args: Args) -> None:

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

    pool = MyPool(args.procs_no)
    pool.map(function, exp_args)


# --------------------------------------------
# Start and detach experiments using nohup

def get_max_procs(state: LiftoffState) -> int:
    """Limit the number of processes by either CPU usage or GPU usage"""
    if state.gpus:
        return min(state.procs_no, sum(state.per_gpu.values()))
    return state.procs_no


def launch(py_file: str,
           exp_args: Args,
           timestamp: int,
           ppid: int,
           root_path: str,
           env: Optional[str],
           gpu: Optional[int] = None,
           omp: Optional[int] = 0,
           mkl: Optional[int] = 0) -> PID:

    err_path = os.path.join(exp_args.out_dir, "err")
    out_path = os.path.join(exp_args.out_dir, "out")

    start_path = os.path.join(exp_args.out_dir, '.__start')
    end_path = os.path.join(exp_args.out_dir, '.__end')
    crash_path = os.path.join(exp_args.out_dir, '.__crash')

    env_vars = ""

    if mkl and mkl > 0:
        env_vars = f"MKL_NUM_THREADS={mkl:d} {env_vars:s}"

    if omp and omp > 0:
        env_vars = f"OMP_NUM_THREADS={omp:d} {env_vars:s}"

    if gpu is not None:
        env_vars = f"CUDA_VISIBLE_DEVICES={gpu:d} {env_vars:s}"

    if env:
        env_vars = f"source activate {env:s}; {env_vars:s}"

    cmd = f" date +%s 1> {start_path:s} 2>/dev/null &&" +\
          f" nohup sh -c '{env_vars:s} python -u {py_file:s}" +\
          f" --configs-dir {exp_args.cfg_dir:s}" +\
          f" --config-file cfg" +\
          f" --default-config-file cfg" +\
          f" --out-dir {exp_args.out_dir:s}" +\
          f" --timestamp {timestamp:d} --ppid {ppid:d}" +\
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


def get_command(pid: PID) -> str:
    result = subprocess.run(f"ps -p {pid:d} -o cmd h",
                            stdout=subprocess.PIPE,
                            shell=True)
    return result.stdout.decode("utf-8").strip()


def still_active(pid: PID, py_file: str) -> bool:
    cmd = get_command(pid)
    if cmd:
        return py_file in cmd
    return False


def dump_pids(path, pids):
    with open(os.path.join(path, "active_pids"), "w") as file_handler:
        for pid in pids:
            file_handler.write(f"{pid:d}\n")


def check_web_server(state: LiftoffState,
                     sock: socket.socket,
                     sel: selectors.EpollSelector,
                     port: int) -> None:
    events = sel.select(timeout=0)
    for key, mask in events:
        if key.data is None:
            new_conn, addr = sock.accept()
            print("New connection from", addr)
            new_conn.setblocking(False)
            new_data = SimpleNamespace(addr=addr, inb=b'', outb=b'')
            new_events = selectors.EVENT_READ | selectors.EVENT_WRITE
            sel.register(new_conn, new_events, data=new_data)
        else:
            conn = key.fileobj
            data = key.data
            if mask & selectors.EVENT_READ:
                recv_data = conn.recv(1024)
                if recv_data:
                    data.inb += recv_data
                    state.process_commands(data)
                else:
                    print("Closing connection to ", data.addr)
                    sel.unregister(conn)
                    conn.close()
            if mask & selectors.EVENT_WRITE:
                if data.outb:
                    sent = conn.send(data.outb)
                    data.outb = data.outb[sent:]
    if np.random.sample() < (1. / 60):
        print("Don't forget: I'm listening on port", port)


def run_from_system(state: LiftoffState,
                    server: Optional[Tuple[socket.socket, selectors.PollSelector, int]],
                    root_path: str, timestamp: int,
                    exp_args: Iterable[Args], args: Args) -> None:
    max_procs_no = get_max_procs(state)
    assert max_procs_no > 0, "You would have been waiting in vain..."
    crt_pid = os.getpid()
    print(f"PID of current process is {crt_pid:d}.")
    print("The maximum number of experiments in parallel will be: ",
          max_procs_no)

    py_file = args.module
    py_file = py_file if py_file.endswith(".py") else py_file + ".py"
    if not os.path.isfile(py_file):
        raise FileNotFoundError("Could not find {py_file:s}.")

    env = value_of(args, "env", None)

    active_procs: Dict[int, List[PID]] = {}
    active_pids: List[int] = []

    for next_args in exp_args:
        while True:
            old_active_procs = active_procs
            active_procs, active_pids = {}, []
            changed = False
            for (gpu, pids) in old_active_procs.items():
                for pid in pids:
                    if still_active(pid, py_file):
                        active_procs.setdefault(gpu, []).append(pid)
                        active_pids.append(pid)
                    else:
                        changed = True
                        print(f"Process {pid:d} seems to be done.")

            if changed:
                dump_pids(root_path, active_pids)

            if len(active_pids) < get_max_procs(state):
                break
            else:
                check_web_server(state, *server)
                time.sleep(1)

        gpu = None
        for gpu_j in state.gpus:
            if len(active_procs.get(gpu_j, [])) < state.per_gpu[gpu_j]:
                gpu = gpu_j
                break
        new_pid = launch(py_file, next_args, timestamp, crt_pid, root_path,
                         env, gpu=gpu, omp=args.omp, mkl=args.mkl)
        active_procs.setdefault(gpu, []).append(new_pid)
        active_pids.append(new_pid)
        dump_pids(root_path, active_pids)

    wait_time = 1
    while active_pids:
        time.sleep(wait_time)
        wait_time = min(wait_time + 1, 30)
        old_active_pids = active_pids
        active_pids = []
        changed = False
        for pid in old_active_pids:
            if still_active(pid, py_file):
                active_pids.append(pid)
            else:
                changed = True
                wait_time = 1
                print(f"Process {pid:d} seems to be done.")
        if changed and active_pids:
            dump_pids(root_path, active_pids)
            print("Still active: " +
                  ",".join([str(pid) for pid in active_pids]) +
                  ". Stop this at any time with no risks.")

    print(clr("All done!", attrs=["bold"]))


def evolve():
    welcome()
    args = parse_args()
    print(config_to_string(args))

    # Make sure configuration files are ok

    assert hasattr(args, "experiment"), "Must specify experiment"
    experiment_path = f"{args.configs_dir}/{args.experiment:s}"
    assert os.path.isdir(experiment_path)
    assert os.path.isfile(f"{experiment_path}/default.yaml")
    assert os.path.isfile(f"{experiment_path:s}/genotype.yaml")

    root_path: str = None
    timestamp: Optional[int] = None
    if hasattr(args, "timestamp") and args.timestamp is not None:
        timestamp = int(args.timestamp)

    if args.resume:
        # -------------------- RESUMING A PREVIOUS EXPERIMENT -----------------
        experiment = args.experiment
        if timestamp:
            previous = [f for f in os.listdir("./results/")
                        if f.startswith(str(timestamp))
                        and f.endswith(experiment)]
            if not previous:
                raise Exception(
                    f"No previous experiment with timestamp {timestamp:d}.")
        else:
            previous = [f for f in os.listdir("./results/")
                        if re.match(f"\\d+_{experiment:s}", f)]
            if not previous:
                raise Exception(f"No previous experiment {experiment:s}.")

        last_time = str(max([int(f.split("_")[0]) for f in previous]))
        print("Resuming", last_time, "!")
        root_path = os.path.join("results", f"{last_time:s}_{experiment:s}")
        timestamp = int(last_time)
        if not os.path.isdir(root_path):
            raise Exception(f"{root_path:s} is not a folder.")
        with open(os.path.join(root_path, ".__timestamp"), "r") as t_file:
            if int(t_file.readline().strip()) != timestamp:
                raise Exception(f"{root_path:s} has the wrong timestamp.")

    else:
        # -------------------- STARTING A NEW EXPERIMENT --------------------
        timestamp = int(time.time())
        root_path = f"results/{timestamp:d}_{args.experiment:s}/"
        while os.path.exists(root_path):
            timestamp = int(time.time())
            root_path = f"results/{timestamp:d}_{args.experiment:s}/"
        os.makedirs(root_path)
        with open(os.path.join(root_path, ".__timestamp"), "w") as t_file:
            t_file.write(f"{timestamp:d}\n")

        shutil.copyfile(os.path.join(experiment_path, "genotype.yaml"),
                        os.path.join(root_path, "genotype.yaml"))

    with open(os.path.join(root_path, ".__ppid"), "w") as ppid_file:
        ppid_file.write(f"{os.getpid():d}\n")
    if args.comment:
        with open(os.path.join(root_path, ".__comment"), "w") as comment_file:
            comment_file.write(args.comment)

    # You need to build the generator

    # -- Copy other files given by the user at the beginning ----

    to_run_path = os.path.join(root_path, "to_run")
    if not os.path.isdir(to_run_path):
        os.makedirs(to_run_path)
    manual_path = os.path.join(experiment_path, "manual")

    if os.path.isdir(manual_path):
        for fname in os.listdir(manual_path):
            if fname.endswith(".yaml"):
                shutil.copyfile(os.path.join(manual_path, fname),
                                os.path.join(to_run_path, fname))

    # -- END of copying manually added files

    state = LiftoffState(args, evolves=True)
    exp_args = genetic_search(state, root_path, args)

    # At this point you need to have root_path, exp_args, timestamp, exp_args

    if args.no_detach:
        with open(os.path.join(root_path, ".__mode"), "w") as m_file:
            m_file.write("multiprocess\n")
        spawn_from_here(exp_args, args)
    else:
        with open(os.path.join(root_path, ".__mode"), "w") as m_file:
            m_file.write("nohup\n")
        sel = selectors.DefaultSelector()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = 9876
        while True:
            try:
                sock.bind(("127.0.0.1", port))
                break
            except OSError as _exc:
                port = np.random.randint(9000, 20000)
        print("Port is", port)
        sock.listen()
        sock.setblocking(False)
        sel.register(sock, selectors.EVENT_READ, data=None)
        run_from_system(state, (sock, sel, port),
                        root_path, timestamp, exp_args, args)


def main():
    welcome()
    args = parse_args()

    print(config_to_string(args))

    # Read configuration files

    cfgs = read_config(strict=False)
    cfg0 = cfgs if not isinstance(cfgs, list) else cfgs[0]
    cfgs = [cfgs] if not isinstance(cfgs, list) else cfgs

    root_path: str = None
    timestamp: Optional[int] = None
    if hasattr(args, "timestamp") and args.timestamp is not None:
        timestamp = int(args.timestamp)

    if args.resume:
        # -------------------- RESUMING A PREVIOUS EXPERIMENT -----------------
        experiment = cfg0.experiment
        if timestamp:
            previous = [f for f in os.listdir("./results/")
                        if f.startswith(str(timestamp))
                        and f.endswith(experiment)]
            if not previous:
                raise Exception(
                    f"No previous experiment with timestamp {timestamp:d}.")
        else:
            previous = [f for f in os.listdir("./results/")
                        if re.match(f"\\d+_{experiment:s}", f)]
            if not previous:
                raise Exception(f"No previous experiment {experiment:s}.")

        last_time = str(max([int(f.split("_")[0]) for f in previous]))
        print("Resuming", last_time, "!")
        root_path = os.path.join("results", f"{last_time:s}_{experiment:s}")
        timestamp = int(last_time)
        if not os.path.isdir(root_path):
            raise Exception(f"{root_path:s} is not a folder.")
        with open(os.path.join(root_path, ".__timestamp"), "r") as t_file:
            if int(t_file.readline().strip()) != timestamp:
                raise Exception(f"{root_path:s} has the wrong timestamp.")

    else:
        # -------------------- STARTING A NEW EXPERIMENT --------------------
        timestamp = int(time.time())
        root_path = f"results/{timestamp:d}_{cfg0.experiment:s}/"
        while os.path.exists(root_path):
            timestamp = int(time.time())
            root_path = f"results/{timestamp:d}_{cfg0.experiment:s}/"
        os.makedirs(root_path)
        with open(os.path.join(root_path, ".__timestamp"), "w") as t_file:
            t_file.write(f"{timestamp:d}\n")

    with open(os.path.join(root_path, ".__ppid"), "w") as ppid_file:
        ppid_file.write(f"{os.getpid():d}\n")
    if args.comment:
        with open(os.path.join(root_path, ".__comment"), "w") as comment_file:
            comment_file.write(args.comment)

    if len(cfgs) == 1 and args.runs_no == 1:
        with open(os.path.join(root_path, ".__mode"), "w") as m_file:
            m_file.write("single\n")

        cfg = cfgs[0]

        # Check if .__end file is already there (experiment is over)
        end_file = os.path.join(root_path, ".__end")
        if os.path.isfile(end_file):
            print(f"Skipping {cfgs[0].title:s}. {end_file:s} exists.")
            return

        crash_file = os.path.join(root_path, ".__crash")
        if os.path.isfile(crash_file):
            os.remove(crash_file)

        # Dump config file if there is none
        cfg_file = os.path.join(root_path, "cfg.yaml")
        if not os.path.isfile(cfg_file):
            with open(cfg_file, "w") as yaml_file:
                yaml.safe_dump(namespace_to_dict(cfg), yaml_file,
                               default_flow_style=False)
        open(os.path.join(root_path, ".__leaf"), "a").close()
        cfg.out_dir, cfg.run_id = root_path, 0
        get_function(args)(cfg)
        return

    exp_args = get_exp_args(cfgs, root_path, args.runs_no)

    if args.no_detach:
        with open(os.path.join(root_path, ".__mode"), "w") as m_file:
            m_file.write("multiprocess\n")
        spawn_from_here(exp_args, args)
    else:
        state = LiftoffState(args, evolves=False)
        with open(os.path.join(root_path, ".__mode"), "w") as m_file:
            m_file.write("nohup\n")
        sel = selectors.DefaultSelector()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = 9876
        while True:
            try:
                sock.bind(("127.0.0.1", port))
                break
            except OSError:
                port = np.random.randint(9000, 20000)
        print("Port is", port)
        sock.listen()
        sock.setblocking(False)
        sel.register(sock, selectors.EVENT_READ, data=None)
        run_from_system(state, (sock, sel, port),
                        root_path, timestamp, exp_args, args)


if __name__ == "__main__":
    main()
