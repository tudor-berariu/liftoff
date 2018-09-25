import os
import re
import sys
import zipfile
from typing import Dict, List, Optional, Tuple, Union
from argparse import ArgumentParser, Namespace
import yaml
from termcolor import colored as clr
from .config import namespace_to_dict


__all__ = ["collect_results", "collect_all_results", "commit"]


Args = Namespace


TO_IGNORE = [".__leaf",
             ".__timestamp", ".__ppid", ".__mode", ".__comment",
             ".__start", ".__end", ".__crash"]


def parse_commit_args() -> Args:
    arg_parser = ArgumentParser()
    arg_parser.add_argument(
        "-e", "--experiment", type=str, dest="experiment",
        help="Get by name.")
    arg_parser.add_argument(
        "-t", "--timestamp", type=str, dest="timestamp",
        help="Get by timestamp.")
    arg_parser.add_argument(
        "-d", "--results-dir", dest="results_dir", default="results",
        help="Results directory (default: ./results)")

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
                    results_dir: str = './results') -> List[
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

    # --- Find the requested experiment folder

    assert os.path.isdir(results_dir), clr(
        f"Wrong path to the results folder. Check the `results_dir` argument.",
        'red', attrs=['bold'])

    if experiment_full_name:
        exp_dirs = [experiment_full_name]
    else:
        exp_dirs: List[str] = os.listdir(results_dir)

    if experiment_name:
        regex: str = f"\\d+_{experiment_name:s}"
        exp_dirs = [f for f in exp_dirs if re.match(regex, f)]

    if timestamp:
        exp_dirs = [f for f in exp_dirs if f.startswith(timestamp)]

    if not exp_dirs:
        raise FileNotFoundError

    dir_name: str
    if len(exp_dirs) > 1:
        latest: int = 0
        dir_name = None
        for exp_dir in exp_dirs:
            if not re.match("\\d+_.*", exp_dir):
                continue
            exp_time = int(exp_dir.split("_")[0])
            if exp_time > latest:
                latest, dir_name = exp_time, exp_dir
    else:
        dir_name = exp_dirs[0]

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

    root_path: str = os.path.join(results_dir, dir_name)
    for rel_path, dirs, files in os.walk(root_path):
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


def collect_all_results(timestamp: Optional[str] = None,
                        experiment_name: Optional[str] = None,
                        conditions: Union[Namespace, dict] = None,
                        names: List[str] = None,
                        incomplete: bool = True,
                        results_dir: str = './results') -> List[
                            Tuple[str, List[str]]]:
    """
        Returns the list of lists of paths for all requested experiments
        in folder 'results/' with name that match //d_*'
    """

    results = []

    exp_dirs: List[str] = os.listdir(results_dir)

    regex: str = f"\\d+_.*"
    exp_dirs = [f for f in exp_dirs if re.match(regex, f)]

    for exp_dir in exp_dirs:
        r = collect_results(timestamp, experiment_name, exp_dir,
            conditions, names, incomplete)
        if len(r) > 0:
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

    assert os.path.isdir(args.results_dir), clr(
        f"Wrong path to the results folder. Check the `results_dir` argument.",
        'red', attrs=['bold'])

    # get dir names in the results dir
    exp_names = [name for name in os.listdir(args.results_dir)
                 if os.path.isdir(f'{args.results_dir}/{name}')]
    assert exp_names, clr(
        f'You have no experiments in your {args.results_dir} folder.',
        'red', attrs=['bold'])

    # zip the last experiment
    last_exp_name = sorted(exp_names)[-1]
    zipf = zipfile.ZipFile(f'{args.results_dir}/{last_exp_name}.zip', 'w',
                           zipfile.ZIP_DEFLATED)
    dir_to_zip(zipf,
               path=f'{args.results_dir}/{last_exp_name}',
               base_path=f'{args.results_dir}/{last_exp_name}')
    zipf.close()
