""" Here we define some functions that might be useful in more than one
    script.
"""

from datetime import datetime
import os.path
import yaml


def is_yaml(path: str) -> bool:
    """ Checks if path points to a config file.
    """
    if not os.path.isfile(path):
        return False

    try:
        with open(path) as handler:
            yaml.load(handler, Loader=yaml.SafeLoader)
    except yaml.ScannerError:
        return False

    return True


def is_experiment(path: str) -> bool:
    """ Checks if given path contains a liftoff experiment (i.e. it is a folder
        that has a .__experiment file).
    """
    if not os.path.isdir(path):
        return False
    if not os.path.isfile(os.path.join(path, ".__experiment")):
        return False
    return True


def get_experiment_paths(  # pylint: disable=bad-continuation
    experiment: str, results_path: str, timestamp_fmt: str, latest: bool = False
) -> str:
    """ Returns the latest experiment with the given name and the given
        timestamp_fmt.
    """
    if experiment is None:
        experiment = ""
    if latest:
        latest_timestamp, latest_experiment_path = None, None
    else:
        experiment_paths = []
    if not os.path.isdir(results_path):
        return []
    with os.scandir(results_path) as fit:
        for entry in fit:
            if is_experiment(entry.path) and experiment in entry.name:
                if latest:
                    parts = entry.name.split("_")
                    try:
                        timestamp = datetime.strptime(parts[0], timestamp_fmt)
                    except ValueError:
                        continue
                    if not latest_timestamp or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_experiment_path = entry.path
                else:
                    experiment_paths.append(entry.path)
    if latest:
        return [latest_experiment_path]
    return experiment_paths


def experiment_matches(run_path, filters):
    """Here we take the run_path and some filters and check if the config there matches
    those filters.
    """
    with open(os.path.join(run_path, "cfg.yaml")) as handler:
        cfg = yaml.load(handler, Loader=yaml.SafeLoader)

    assert isinstance(filters, list)
    assert all(len(flt.split("=")) == 2 for flt in filters)

    # TODO: I think there's a bug in this code, need to check this is the intended
    # usage. When two filters are provided, eg.: `[a.b=c, x.y=z]`, this function will
    # return after checking the first filter only.
    for flt in filters:
        keys, value = flt.split("=")
        keys = keys.split(".")
        crt_cfg = cfg
        for key in keys[:-1]:
            if key not in crt_cfg:
                return False
            else:
                assert isinstance(crt_cfg[key], dict)
                crt_cfg = crt_cfg[key]
        try:
            if value == "None":
                return crt_cfg[keys[-1]] is None
            if crt_cfg[keys[-1]] != type(crt_cfg[keys[-1]])(value):
                return False
        except Exception as exception:  # pylint: disable=broad-except
            print(exception)
            return False
    return True
