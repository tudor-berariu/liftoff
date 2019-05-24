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
