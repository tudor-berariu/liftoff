""" Liftoff utils related to retrieving the results of the experiments.
"""
import os
import sys
import zipfile
from typing import Dict, List, Optional, Tuple, Union
from argparse import ArgumentParser, Namespace
import yaml

from .common.argparsers import add_experiment_lookup_args
from .common.lookup import get_latest_experiment, get_experiments
from .config import namespace_to_dict


__all__ = ["collect_results", "collect_all_results", "commit"]


Args = Namespace


TO_IGNORE = [".__leaf",
             ".__timestamp", ".__ppid", ".__mode", ".__comment",
             ".__start", ".__end", ".__crash"]


def parse_commit_args() -> Args:
    arg_parser = ArgumentParser()
    add_experiment_lookup_args(arg_parser)
    return arg_parser.parse_args()


def check(conditions: dict, config_data: dict) -> bool:
    for (key, value) in conditions.items():
        c_value = config_data[key]  # raises Exception if not found
        if isinstance(value, dict):
            if not check(value, c_value):
                return False
        else:  # TODO: check more complex situatuations e.g. lists of dicts
            if not (value == c_value):
                return False
    return True


def collect_results(timestamp: Optional[str] = None,
                    experiment_name: Optional[str] = None,
                    experiment_full_name: Optional[str] = None,
                    conditions: Union[Namespace, dict] = None,
                    names: List[str] = None,
                    incomplete: bool = True,
                    results_dir: str = './results',
                    timestamp_fmt: str = "%Y%b%d-%H%M%S") -> List[
                        Tuple[str, List[str]]]:
    """Returns the list of lists of paths for requested experiment.

    If :timestamp: is given, that specific experiment is used. If
    :experiment_name: is given, then the latest experiment with that
    name is used. If neither :timestamp:, nor :experiment_name: is
    given, then the latest experiment is being used.

    From each individual run in that experiment the paths to the files
    listed in :names: are collected. If :names: is None, all files
    except liftoff's .__start, .__end, .__crash, or .__leaf are
    collected. If :names: is an empty list, then no file will be
    collected (this is useful if you need the paths to all individual
    runs' folders).

    If :incomplete: is true, the latest version of a file from an
    unfinished run is used. E.g. if "results.pkl" is one of the
    elements in :names:, and in some folder the following files are
    being found: "step__1000__results.pkl", "step_2000_results.pkl",
    the latter will be selected. Intermediate files should be named
    like this: ".+__<number>__<name>". Use '__' as a delimiter, but do
    not use '__' in <name>. Use <number> for epochs, number of
    transitions seen by your agent or any other *increasing* variable.

    If :conditions: is given, then individual runs are
    filtered. Conditions should be a namespace or a dictionary
    following the strcture of the arguments given to the script. E.g.:
    Namespace(model=Namespace(hidden_units=300), epochs=10) or
    {"model": {"hidden_units": 300}, "epochs": 30}.

    For now, if you need files from subfolders, just get them
    yourself. Support for such cases will be added soon.

    """

    if experiment_full_name is not None:
        sep_idx = experiment_full_name.index("_")
        timestamp = experiment_full_name[:sep_idx]
        experiment_name = experiment_full_name[sep_idx + 1:]

    _exp_name, exp_path = get_latest_experiment(experiment=experiment_name,
                                                timestamp=timestamp,
                                                timestamp_fmt=timestamp_fmt,
                                                results_dir=results_dir
                                                )
    # --- Collect files

    conds: dict
    if conditions:
        if isinstance(conditions, Namespace):
            conds = namespace_to_dict(conditions)
        else:
            conds = conditions
    else:
        conds = {}

    results: List[Tuple[str, List[str]]] = []

    for rel_path, dirs, files in os.walk(exp_path):
        if ".__leaf" not in files:
            continue
        if dirs:
            print("Warning: there are directories,"
                  " but they are not currently collected."
                  " Use the path to see what's there.", file=sys.stderr)

        if conds:
            with open(os.path.join(rel_path, "cfg.yaml")) as handler:
                config_data = yaml.load(handler, Loader=yaml.SafeLoader)
            if not check(conds, config_data):
                continue

        if names == []:
            results.append((rel_path, []))
            continue

        user_files = [f for f in files if f not in TO_IGNORE]
        to_return: List[str]
        if incomplete:
            versions: Dict[str, Tuple[int, str]] = {}
            for file_name in user_files:
                parts = file_name.split("__")
                if names is not None and parts[-1] not in names:
                    continue  # We don't need this file
                if len(parts) == 1:
                    versions[file_name] = (-1, file_name)
                elif parts[-1] in versions:
                    old_step, _ = versions[parts[-1]]
                    if old_step > 0 and old_step < int(parts[-2]):
                        versions[parts[-1]] = (int(parts[-2]), file_name)
                else:
                    versions[parts[-1]] = (int(parts[-2]), file_name)
            to_return = [v[1] for v in versions.values()]
        elif names is not None:  # Just to be clear: None and [] are different
            to_return = [f for f in user_files if f in names]
        else:
            to_return = user_files

        results.append((rel_path, to_return))

    return results


def collect_all_results(experiment_names: List[str],
                        conditions: Union[Namespace, dict] = None,
                        names: List[str] = None,
                        incomplete: bool = True,
                        results_dir: str = './results') -> List[
                            Tuple[str, List[str]]]:
    """ Returns **all** the experiments, at all timestamps, for each of the
        names in `experiment_names`.
    """

    assert isinstance(
        experiment_names, list
    ), "Pass a list of experiment names."

    results = []
    exp_dirs = get_experiments(experiment_names, results_dir)

    for exp_dir in exp_dirs:
        r = collect_results(
            timestamp=None,
            experiment_name=None,
            experiment_full_name=exp_dir,
            conditions=conditions,
            names=names,
            incomplete=incomplete,
            results_dir=results_dir)
        if r:
            results.append(r)

    return results


ZipFile = zipfile.ZipFile


def dir_to_zip(zip_handle: ZipFile, path: str, base_path: str = ""):
    """
    Adding directory given by `path` to opened zip file `zip_handle`

    @param base_path path that will be removed from `path` when adding to
    archive

    Examples:
        add whole "dir" to "test.zip" (when you open "test.zip" you will see
        only "dir")
        ```
        zip_handle = zipfile.ZipFile('test.zip', 'w')
        addDirToZip(zip_handle, 'dir')
        zip_handle.close()
        ```

        add contents of "dir" to "test.zip" (when you open "test.zip" you will
        see only it's contents)
        ```
        zip_handle = zipfile.ZipFile('test.zip', 'w')
        addDirToZip(zip_handle, 'dir', 'dir')
        zip_handle.close()
        ```

        add contents of "dir/subdir" to "test.zip" (when you open "test.zip"
        you will see only contents of "subdir")
        ```
        zip_handle = zipfile.ZipFile('test.zip', 'w')
        addDirToZip(zip_handle, 'dir/subdir', 'dir/subdir')
        zip_handle.close()
        ```

        add whole "dir/subdir" to "test.zip" (when you open "test.zip" you will
        see only "subdir")
        ```
        zip_handle = zipfile.ZipFile('test.zip', 'w')
        addDirToZip(zip_handle, 'dir/subdir', 'dir')
        zip_handle.close()
        ```

        add whole "dir/subdir" with full path to "test.zip" (when you open
        "test.zip" you will see only "dir" and inside it only "subdir")
        ```
        zip_handle = zipfile.ZipFile('test.zip', 'w')
        addDirToZip(zip_handle, 'dir/subdir')
        zip_handle.close()
        ```

        add whole "dir" and "otherDir" (with full path) to "test.zip" (when you
        open "test.zip" you will see only "dir" and "otherDir")
        ```
        zip_handle = zipfile.ZipFile('test.zip', 'w')
        addDirToZip(zip_handle, 'dir')
        addDirToZip(zip_handle, 'otherDir')
        zip_handle.close()
        ```
    """
    base_path = base_path.rstrip("\\/") + ""
    base_path = base_path.rstrip("\\/")
    for root, _, files in os.walk(path):
        # add dir itself (needed for empty dirs
        dir_path = os.path.join(root, ".")
        print(f'compressing files in {dir_path}')
        zip_handle.write(dir_path)
        # add files
        for file in files:
            file_path = os.path.join(root, file)
            in_zip_path = file_path.replace(base_path, "", 1).lstrip("\\/")
            # print file_path + " , " + in_zip_path
            zip_handle.write(file_path, in_zip_path)


def commit() -> None:
    """ Takes the last experiment it finds and archives it.
    """
    args = parse_commit_args()
    _exp_name, exp_path = get_latest_experiment(**args.__dict__)
    zipf = zipfile.ZipFile(f'{exp_path:s}.zip', 'w', zipfile.ZIP_DEFLATED)
    dir_to_zip(zipf, path=exp_path, base_path=exp_path)
    zipf.close()
