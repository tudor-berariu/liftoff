""" Here we implement the script that prepares an experiment to be run with
    liftoff.

    There are two intended use cases for this script:

    1) For experiments defined by two files 'default.yaml' and 'config.yaml':

        liftoff <config-dir>

    2) For experiments defined by a single file you want to run multiple times:

        liftoff <config-file>

    Both command support the following command line arguments:
        --name <new-name>
        --runs-no <runs-nu>
        --timestamp-fmt <timestamp-fmt>
        --experiments-dir <experiments-dir>
        --append-to <experiment-full-name>
        --dry-run
"""

from argparse import Namespace
from datetime import datetime
from copy import copy, deepcopy
import itertools
import os.path
import string
import pyperclip
from termcolor import colored as clr
import yaml

from .common.dict_utils import clean_dict, deep_update_dict, hashstr, uniqstr
from .common.options_parser import OptionParser


VALID_CHARS = f"-_.(){string.ascii_letters:s}{string.digits:s}"
KNOWN_CONSTRAINTS = ["->", "<=>", "v", "!!"]


def safe_file_name(title: str):
    """ Replaces all symbols except those in VALID_CHARS with '_'.
    """
    return "".join(map(lambda c: c if c in VALID_CHARS else "_", title))


def parse_options(strict: bool = True) -> Namespace:
    """ Parse command line arguments and liftoff configuration.
    """

    opt_parser = OptionParser(
        "liftoff-prepare",
        [
            "config_path",
            "name",
            "runs_no",
            "timestamp_fmt",
            "results_path",
            "append_to",
            "do",
            "overwrite",
            "verbose",
            "copy_to_clipboard"
        ],
    )

    return opt_parser.parse_args(strict=strict)


def idxs_of_duplicates(lst):
    """ Returns the indices of duplicate values.
    """
    idxs_of = dict({})
    dup_idxs = []
    for idx, value in enumerate(lst):
        idxs_of.setdefault(value, []).append(idx)
    for idxs in idxs_of.values():
        if len(idxs) > 1:
            dup_idxs.extend(idxs)
    return dup_idxs


def var_names(variables):
    """ Computes all non-ambiguous names a variable might take.
    """
    name_to_var = dict({})
    names = []
    lengths = [1 for _ in variables]
    candidates = [".".join(v[-l:]) for (v, l) in zip(variables, lengths)]
    dup_idxs = idxs_of_duplicates(candidates)
    while dup_idxs:
        for idx in dup_idxs:
            lengths[idx] = length = min(len(variables[idx]), lengths[idx] + 1)
            candidates[idx] = ".".join(variables[idx][-length:])
        dup_idxs = idxs_of_duplicates(candidates)
    for idx, (var, length) in enumerate(zip(variables, lengths)):
        vnames = [".".join(var[-l:]) for l in range(length, len(var) + 1)]
        names.append(vnames)
        for name in vnames:
            name_to_var[name] = idx

    return names, name_to_var


def check(values, constraints):
    """ Checks the given assignment against given constraints.
    """
    for idx0, idx1, restrictions in constraints:
        should_del0, should_del1 = False, False
        for rtype, pairs in restrictions.items():
            if rtype == "->":
                for val0, val1 in pairs:
                    if val0 == values[idx0]:
                        if values[idx1] != val1:
                            return False
                        if val1 == "delete":
                            should_del1 = True
                        break
            elif rtype == "<=>":
                for val0, val1 in pairs:
                    if val0 == values[idx0]:
                        if values[idx1] != val1:
                            return False
                        if val1 == "delete":
                            should_del1 = True
                        break
                    if val1 == values[idx1]:
                        if values[idx0] != val0:
                            return False
                        if val0 == "delete":
                            should_del0 = True
                        break
            elif rtype == "v":
                for val0, val1 in pairs:
                    if val0 != values[idx0] and val1 != values[idx1]:
                        return False
            elif rtype == "!!":
                for val0, val1 in pairs:
                    if val0 == values[idx0] and val1 == values[idx1]:
                        return False
            else:
                raise NotImplementedError
        if values[idx0] == "delete" and not should_del0:
            return False
        if values[idx1] == "delete" and not should_del1:
            return False
    return True


def generate_combinations(cfg, opts):
    """ This is actually the function we wrote the whole script for.
    """

    if "liftoff" in cfg:
        constraints = cfg["liftoff"]
        del cfg["liftoff"]
        if not isinstance(constraints, list):
            raise ValueError(f"Expected list of constraints, got {constraints}")
    else:
        constraints = []

    queue = [(cfg, [])]
    var_id = 0
    variables, domains = [], []

    while queue:
        node, parent = queue.pop()
        if isinstance(node, list):
            variables.append(copy(parent))
            domains.append(deepcopy(node))
            var_id += 1
        elif isinstance(node, dict):
            for name, value in node.items():
                queue.append((value, parent + [name]))
        else:
            raise ValueError(f"Encountered {node} in experiment configuraiton")

    all_names, name_to_var = var_names(variables)

    print(clr(f"\nFound {len(variables):d} variables:", attrs=["bold"]))
    width = max(len(names[0]) for names in all_names)
    for names, domain in zip(all_names, domains):
        print(f"\t{names[0]:{width + 2}s} with {len(domain):d} values")

    new_constraints = []
    for constraint in constraints:
        if not isinstance(constraint, dict):
            raise ValueError(f"Expected dict for constraint, not {constraint}")
        if "vars" not in constraint:
            raise ValueError(f"Expected 'vars' in constraint {constraint}")
        cvars = constraint["vars"]
        if (  # pylint: disable=bad-continuation
            len(cvars) != 2
            or cvars[0] not in name_to_var
            or cvars[1] not in name_to_var
        ):
            raise ValueError(f"Could not indetify vars in {cvars}")
        idx0, idx1 = name_to_var[cvars[0]], name_to_var[cvars[1]]
        var0, var1 = all_names[idx0][-1], all_names[idx1][-1]
        restrictions = {}
        for key, values in constraint.items():
            if key != "vars":
                if key not in KNOWN_CONSTRAINTS:
                    raise ValueError(f"Strainge constraint {key}")
                if not isinstance(values, list):
                    raise ValueError(f"Expected list of pairs not {values}")
                for val0, val1 in values:
                    if val0 not in domains[idx0]:
                        if val0 == "delete":
                            domains[idx0].append("delete")
                        else:
                            raise ValueError(f"{val0} not in {var0}'s domain'")
                    if val1 not in domains[idx1]:
                        if val1 == "delete":
                            domains[idx1].append("delete")
                        else:
                            raise ValueError(f"{val1} not in {var1}'s domain'")
                restrictions[key] = values

        new_constraints.append((idx0, idx1, restrictions))
    constraints = new_constraints

    print(clr("\nConstraints:", attrs=["bold"]))
    for idx0, idx1, restrictions in constraints:

        name0, name1 = all_names[idx0][0], all_names[idx1][0]
        for rtype, values in restrictions.items():
            if rtype in ["->", "<=>", "v"]:
                print("\t", end="")
                print(
                    " & ".join(
                        [
                            f"{name0}={v0} {rtype} {name1}={v1}"
                            for v0, v1 in values
                        ]
                    )
                )
            elif rtype == "!!":
                print("\t", end="")
                print(
                    " & ".join(
                        [f"!({name0}={v0} & {name1}={v1})" for v0, v1 in values]
                    )
                )
    for values in itertools.product(*domains):
        if not constraints or check(values, constraints):
            cfg = {}
            title = []
            for idx, (var, value) in enumerate(zip(variables, values)):
                if value != "delete":
                    title.append(f"{all_names[idx][-1]}={value}")
                dct = cfg
                for parent in var[:-1]:
                    dct = dct.setdefault(parent, {})
                dct[var[-1]] = value

            yield (cfg, "; ".join(title))


def prepare_single_subexperiment(opts: Namespace):
    """ Here we add a single sub-experiment to an experiment.
    """
    with open(opts.config_path) as handler:
        config_data = yaml.load(handler, Loader=yaml.SafeLoader)

    title = os.path.basename(os.path.normpath(opts.config_path))
    if title.endswith(".yaml"):
        title = title[:-5]

    yield config_data, title, {}


def prepare_multiple_subexperiments(opts):
    """ Here we assume there are either two files: config.yaml and default.yaml
        or a bunch of files that will be added as single experiments.
    """

    default_path = os.path.join(opts.config_path, "default.yaml")
    config_path = os.path.join(opts.config_path, "config.yaml")

    with open(config_path) as handler:
        config_data = yaml.load(handler, Loader=yaml.SafeLoader)

    with open(default_path) as handler:
        default_data = yaml.load(handler, Loader=yaml.SafeLoader)

    for exp_cfg, title in generate_combinations(config_data, opts):
        full_cfg = deep_update_dict(deepcopy(default_data), exp_cfg)
        yield full_cfg, title, exp_cfg


def prepare_experiment(opts):

    total_se, new_se, existing_se = 0, 0, 0
    total_runs, new_runs, existing_runs = 0, 0, 0
    written_runs = 0

    experiment_path = None

    if not opts.do:
        print("\nThis will produce no effects. Use --do to create files.")

    if opts.append_to is not None:
        if not os.path.isdir(opts.append_to):
            raise RuntimeError(f"{opts.append_to} is not a folder.")
        if opts.name is not None:
            print("Option --name {opts.name} will be ignored.")
        experiment_path = opts.append_to
    else:
        if opts.name is None:
            name = os.path.basename(os.path.normpath(opts.config_path))
        else:
            name = opts.name
        while True:
            timestamp = f"{datetime.now():{opts.timestamp_fmt:s}}"
            full_name = f"{timestamp:s}_{name:s}/"
            experiment_path = os.path.join(opts.results_path, full_name)
            if not os.path.exists(experiment_path):
                break

    print("")
    print("Will configure experiment in", clr(experiment_path, attrs=["bold"]))

    opts.experiment_path = experiment_path

    if os.path.isfile(opts.config_path):
        new_cfgs = prepare_single_subexperiment(opts)
    elif os.path.isdir(opts.config_path):
        new_cfgs = prepare_multiple_subexperiments(opts)
    else:
        raise RuntimeError(f"Could not find {opts.config_path}")

    start_idx = 0
    existing = dict({})

    if opts.do and not opts.append_to:
        os.makedirs(experiment_path)

    if opts.do:
        open(os.path.join(experiment_path, ".__experiment"), "a").close()

    if opts.append_to:
        for fle in os.scandir(opts.experiment_path):
            if fle.is_dir():
                try:
                    start_idx = max(start_idx, int(fle.name.split("_")[0]) + 1)
                except ValueError:
                    pass
                try:
                    path_parts = [opts.experiment_path, fle.name, ".__cfg_hash"]
                    with open(os.path.join(*path_parts)) as hndlr:
                        cfg_hash = hndlr.readline().strip()
                    existing[cfg_hash] = fle.name
                except FileNotFoundError:
                    pass

        print(f"New experiments will start from index {start_idx:d}.")

    for (full_cfg, title, exp_cfg) in new_cfgs:
        clean_dict(full_cfg)
        total_se += 1
        if opts.verbose and opts.verbose > 0:
            print(f"Adding sub-experiment: {clr(title, attrs=['bold'])}.")
        cfg_hash = hashstr(uniqstr(full_cfg))
        if cfg_hash in existing:

            if opts.verbose and opts.verbose > 0:
                print(f"Sub-xperiment {title} already", clr("exists", "green"))
            path_parts = [opts.experiment_path, existing[cfg_hash]]
            subexperiment_path = os.path.join(*path_parts)
            existing_se += 1
        else:
            candidate_name = safe_file_name(f"{start_idx:04d}_{title:s}")
            if len(candidate_name) < 255:
                path_parts = [opts.experiment_path, candidate_name]
            else:
                hash_name = safe_file_name(f"{start_idx:04d}_{cfg_hash:s}")
                path_parts = [opts.experiment_path, hash_name]
            subexperiment_path = os.path.join(*path_parts)
            if opts.do:
                os.mkdir(subexperiment_path)
                hash_path = os.path.join(subexperiment_path, ".__cfg_hash")
                with open(hash_path, "w") as hndlr:
                    hndlr.writelines([cfg_hash])
            new_se += 1
            start_idx += 1

        # Here we know that subexperiment_path exists
        for run_id in range(opts.runs_no):
            run_path = os.path.join(subexperiment_path, str(run_id))
            total_runs += 1
            if os.path.exists(run_path):
                existing_runs += 1
                if not os.path.isdir(run_path):
                    raise RuntimeError(f"{run_path} is not a folder")
            else:
                new_runs += 1
                if opts.do:
                    os.mkdir(run_path)

            cfg_path = os.path.join(run_path, "cfg.yaml")
            end_path = os.path.join(run_path, ".__end")
            lock_path = os.path.join(run_path, ".__lock")
            leaf_path = os.path.join(run_path, ".__leaf")

            write_files = True
            if os.path.exists(lock_path) or os.path.exists(end_path):
                print(clr(f"{run_path:s} is locked", "red"))
                write_files = False
            elif not opts.overwrite and os.path.exists(cfg_path):
                write_files = False

            written_runs += int(write_files)

            if write_files and opts.do:
                run_cfg = deepcopy(full_cfg)
                run_cfg["out_dir"] = run_path
                run_cfg["run_id"] = run_id
                run_cfg["title"] = title
                if exp_cfg:
                    run_cfg["experiment_arguments"] = exp_cfg

                with open(cfg_path, "w") as yaml_file:
                    yaml.safe_dump(run_cfg, yaml_file, default_flow_style=False)

                open(leaf_path, "a").close()

    print(clr("\nSummary:", attrs=["bold"]))
    print(
        "\tSub-experiments:",
        clr(f"{total_se:d}", attrs=["bold"]),
        "|",
        "New:",
        clr(f"{new_se:d}", attrs=["bold"]),
        "|",
        "Existing:",
        clr(f"{existing_se:d}", attrs=["bold"]),
    )

    print(
        "\tRuns:",
        clr(f"{total_runs:d}", attrs=["bold"]),
        "|",
        "New:",
        clr(f"{new_runs:d}", attrs=["bold"]),
        "|",
        "Existing:",
        clr(f"{existing_runs:d}", attrs=["bold"]),
        "|",
        "Written:",
        clr(f"{written_runs:d}", attrs=["bold"]),
    )

    if not opts.do:
        print(
            "\nThis was just a simultation. Rerun with",
            clr("--do", attrs=["bold"]),
            "to prepare experiment for real.",
        )

        return None

    print(
        "\nExperiment configured in", clr(experiment_path, attrs=["bold"])
    )
    if opts.copy_to_clipboard:
        pyperclip.copy(experiment_path)
        print("Experiment path copied to clipboard.")

    return experiment_path



def prepare(strict: bool = True) -> None:
    """ Main function.
    """
    opts = parse_options(strict=strict)
    prepare_experiment(opts)
