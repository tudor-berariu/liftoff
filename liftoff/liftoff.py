from argparse import ArgumentParser, Namespace
from typing import Callable
from copy import deepcopy
import os
import re
from importlib import import_module
from time import time
import multiprocessing
import multiprocessing.pool
import yaml


from .config import read_config, namespace_to_dict


def parse_args() -> Namespace:
    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "function",
        default="learn.main",
        help="Module and function to be called for each experiment")
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

    return arg_parser.parse_known_args()[0]


def get_function(full_name: str) -> Callable:
    import sys
    sys.path.append(os.getcwd())
    if '.' in full_name:
        parts = full_name.split('.')
        module_name = '.'.join(parts[:-1])
        function_name = parts[-1]
    else:
        module_name = full_name
        function_name = "main"

    module = import_module(module_name)
    function = module.__dict__[function_name]

    return function


def main() -> None:
    args = parse_args()
    print(args)

    # Figure out what should be executed
    function = get_function(args.function)

    # Read configuration files

    cfgs = read_config(strict=False)
    cfg0 = cfgs if not isinstance(cfgs, list) else cfgs[0]
    cfgs = [cfgs] if not isinstance(cfgs, list) else cfgs

    root_path = None
    if args.resume:
        experiment = cfg0.experiment
        previous = [f for f in os.listdir("./results/")
                    if re.match(f"\\d+_{experiment:s}", f)]
        if previous:
            last_time = str(max([int(f.split("_")[0]) for f in previous]))
            print("Resuming", last_time, "!")
            root_path = os.path.join("results",
                                     f"{last_time:s}_{experiment:s}")
            assert os.path.isdir(root_path)

    if root_path is None:
        root_path = f"results/{int(time()):d}_{cfg0.experiment:s}/"
        assert not os.path.exists(root_path)
        os.makedirs(root_path)

    if len(cfgs) == 1 and cfgs[0].runs_no == 1:
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
        function(cfg)
        return

    exp_args = []

    for j, cfg in enumerate(cfgs):
        title = cfg.title
        for char in " -.,=:;/()":
            title = title.replace(char, "_")
        alg_path = os.path.join(root_path, f"{j:d}_{title:s}")
        if not os.path.isdir(alg_path):
            os.makedirs(alg_path, exist_ok=True)
        cfg_file = os.path.join(alg_path, "cfg.yaml")
        if not os.path.isfile(cfg_file):
            with open(cfg_file, "w") as yaml_file:
                yaml.safe_dump(namespace_to_dict(cfg), yaml_file,
                               default_flow_style=False)
        if cfg.runs_no > 1:
            for run_id in range(cfg.runs_no):
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
                exp_args.append(new_cfg)
        else:
            results_file = os.path.join(alg_path, "results.pkl")
            if os.path.isfile(results_file):
                print(f"Skipping {cfg.title:s}. {results_file:s} exists.")
            else:
                cfg.out_dir = alg_path
                cfg.run_id = 0
                exp_args.append(cfg)

    """
    Solution from here: https://stackoverflow.com/a/8963618/1478624
    """

    class NoDaemonProcess(multiprocessing.Process):
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


if __name__ == "__main__":
    main()
