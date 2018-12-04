from argparse import ArgumentParser
import os
import os.path
from datetime import datetime
import yaml


def add_experiment_lookup_args(arg_parser: ArgumentParser):
    arg_parser.add_argument(
        "-e", "--experiment",
        type=str,
        dest="experiment",
        help="Find experiments by name.")
    arg_parser.add_argument(
        "-t", "--timestamp",
        type=str,
        dest="timestamp",
        help="Find experiments by timestamp.")
    arg_parser.add_argument(
        "-d", "--results-dir",
        type=str,
        dest="results_dir",
        default="results",
        help="Results directory (default: ./results)")
    arg_parser.add_argument(
        '--timestamp_fmt',
        type=str,
        dest="timestamp_fmt",
        default="%Y%b%d-%H%M%S",
        help="Default timestamp format.")


def get_latest_experiment(experiment: str = None,
                          timestamp: str = None,
                          timestamp_fmt: str = "%Y%b%d-%H%M%S",
                          results_dir: str = "./results",
                          **_kwargs) -> str:

    if "_" in timestamp_fmt:
        raise ValueError("Unsupported datetime format. No '_'s, please.")

    latest_experiment = None  # type: str
    latest_timestamp = None  # type: datetime

    for dirname in filter(lambda f: f.is_dir(), os.scandir(results_dir)):
        if timestamp is not None and not dirname.name.startswith(timestamp):
            continue

        crt_timestamp_str, *crt_name_parts = dirname.name.split("_")
        crt_name = "_".join(crt_name_parts)

        if experiment is not None and crt_name != experiment:
            continue

        try:
            crt_timestamp = datetime.strptime(crt_timestamp_str, timestamp_fmt)
        except ValueError:
            continue

        if latest_experiment is None or latest_timestamp < crt_timestamp:
            latest_experiment = dirname.name
            latest_timestamp = crt_timestamp

    if latest_experiment is None:
        raise RuntimeError("No experiments found.")

    return latest_experiment, os.path.join(results_dir, latest_experiment)


def update_configs(original, diff):
    for key, value in diff.items():
        if key.startswith("_"):
            original[key[1:]] = value
        elif not isinstance(value, dict) or key not in original:
            original[key] = value
        else:
            if not isinstance(original[key], dict):
                raise RuntimeError("Cannot overwrite value with dictionary.")
            update_configs(original[key], value)


def get_liftoff_config(only_local: bool = False) -> dict:
    local_cfg, global_cfg = None, None

    if os.path.isfile(".liftoff_cfg.yaml"):
        with open(".liftoff_cfg.yaml") as handler:
            local_cfg = yaml.load(handler, Loader=yaml.SafeLoader)
    if not only_local and os.path.isfile("~/.liftoff_cfg.yaml"):
        with open("~/.liftoff_cfg.yaml") as handler:
            global_cfg = yaml.load(handler, Loader=yaml.SafeLoader)

    if global_cfg is None:
        return local_cfg

    if local_cfg is None:
        return global_cfg

    update_configs(global_cfg, local_cfg)
    return global_cfg


def ask_user_yn(question: str) -> bool:
    while True:
        answer = str(input(f"\n{question:s} (y/n): ")).lower().strip()
        if answer == "y":
            return True
        if answer == "n":
            return False


def save_local_options(update_cfg: dict):
    local_cfg = get_liftoff_config(only_local=True)
    if local_cfg is None:
        local_cfg = update_cfg
    else:
        update_configs(local_cfg, update_cfg)
    with open(".liftoff_cfg.yaml", "w") as handler:
        yaml.safe_dump(local_cfg, handler, default_flow_style=False)
