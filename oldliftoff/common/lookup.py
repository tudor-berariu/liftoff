""" Here we define functions find experiment folders matching some search
    criteria (e.g. name, timestamp).
"""


from typing import List, Tuple
import os
from datetime import datetime


def get_experiments(experiment_names: List[str], results_dir: str) -> List[str]:
    """ Receives a list of experiment names and returns tuples of
        (timestamp_name, experiment_path).

    Args:
        experiment_names (List[str]): List of experiments.
        results_dir (str): Parent dir of experiments.

    Returns:
        List[Tuple[str, str]]: List of tuples, see above.
    """
    assert isinstance(
        experiment_names, list
    ), "Pass a list of experiment names."
    results = []
    all_experiments = filter(lambda f: f.is_dir(), os.scandir(results_dir))
    for exp_name in all_experiments:
        for looked_for in experiment_names:
            if looked_for in exp_name.name:
                results.append(exp_name.name)
    return results


def get_latest_experiments(  # pylint: disable=bad-continuation
    experiment: List[str] = None, timestamp: List[str] = None, **kwargs
) -> List[Tuple[str, str]]:
    """ Used when bringing together several experiments.
    """
    result = []
    if experiment and timestamp:
        if len(experiment) != len(timestamp):
            raise ValueError("Experiment names & timestamps must match length")
    elif experiment:
        timestamp = [None] * len(experiment)
    elif timestamp:
        experiment = [None] * len(timestamp)
    else:
        timestamp, experiment = [None], [None]
    for exp, tms in zip(experiment, timestamp):
        name, path = get_latest_experiment(exp, tms, **kwargs)
        result.append((name, path))
    return result


def get_latest_experiment(  # pylint: disable=bad-continuation
    experiment: str = None,
    timestamp: str = None,
    timestamp_fmt: str = "%Y%b%d-%H%M%S",
    results_dir: str = "./results",
    strict_fmt: bool = False,
    **_kwargs,
) -> Tuple[str, str]:
    """ This function returns the experiment with the given timestamp
        (if provided), the latest experiment with the given name (if provided),
        or the latest experiment in general.
    """
    if "_" in timestamp_fmt:
        raise ValueError("Unsupported datetime format. No '_'s, please.")

    full_name = None  # type: str
    latest_timestamp = None  # type: datetime

    for dirname in filter(lambda f: f.is_dir(), os.scandir(results_dir)):
        if timestamp is not None and not dirname.name.startswith(timestamp):
            continue

        crt_timestamp_str, *crt_name_parts = dirname.name.split("_")
        crt_name = "_".join(crt_name_parts)

        if experiment is not None and crt_name != experiment:
            continue

        crt_timestamp = None
        try:
            crt_timestamp = datetime.strptime(crt_timestamp_str, timestamp_fmt)
        except ValueError:
            if strict_fmt:
                continue

        if crt_timestamp is None:
            try:
                t_fmt_path = os.path.join(
                    results_dir, dirname.name, ".__timestamp_fmt"
                )
                with open(t_fmt_path) as t_fmt_file:
                    crt_fmt = t_fmt_file.readline().strip()
                crt_timestamp = datetime.strptime(crt_timestamp_str, crt_fmt)
            except ValueError:
                continue
            except FileNotFoundError:
                continue

        if full_name is None or latest_timestamp < crt_timestamp:
            full_name = dirname.name
            latest_timestamp = crt_timestamp

    if full_name is None:
        raise RuntimeError("No experiments found.")

    return full_name, os.path.join(results_dir, full_name)


def create_new_experiment_folder(  # pylint: disable=bad-continuation
    experiment: str, timestamp_fmt: str, results_dir: str
):
    """ This function creates a new experiment folder.
    """
    if "_" in timestamp_fmt:
        raise ValueError("Unsupported datetime format. No '_'s, please.")

    while True:
        timestamp = f"{datetime.now():{timestamp_fmt:s}}"
        full_name = f"{timestamp:s}_{experiment:s}/"
        experiment_path = os.path.join(results_dir, full_name)
        if not os.path.exists(experiment_path):
            break

    os.makedirs(experiment_path)
    with open(os.path.join(experiment_path, ".__timestamp_fmt"), "w") as tfile:
        tfile.write(f"{timestamp_fmt:s}\n")
    with open(os.path.join(experiment_path, ".__timestamp"), "w") as tfile:
        tfile.write(f"{timestamp:s}\n")

    return full_name, experiment_path
