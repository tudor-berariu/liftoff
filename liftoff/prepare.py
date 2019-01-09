from copy import copy, deepcopy
from itertools import product
from argparse import ArgumentParser, Namespace
from typing import Any, Dict, Iterable, List, Tuple, Union
import os.path
from functools import partial
import yaml
from termcolor import colored as clr

from .common.liftoff_config import get_liftoff_config
from .common.tips import display_tips
from .version import welcome

# Typing

VarId = int
VarPath = List[str]
Variables = Dict[VarId, VarPath]
Domain = List[Any]
Domains = Dict[VarId, Domain]
Assignment = Dict[VarId, Any]
BadPairs = Dict[Tuple[VarId, VarId], List[Tuple[Any, Any]]]


def get_args() -> Namespace:
    """Read command line arguments for liftoff-prepare"""
    arg_parser = ArgumentParser("Prepare experiment for liftoff")
    arg_parser.add_argument(
        "experiment", type=str, help="Experiment to prepare"
    )
    arg_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        dest="force",
        help="Delete other generated files if found.",
    )
    arg_parser.add_argument(
        "-c",
        "--clean",
        action="store_true",
        default=False,
        dest="clean",
        help="Deletes generated files if found.",
    )

    return arg_parser.parse_args()


def check_paths(experiment: str, clean: bool = False) -> Tuple[str, str]:
    """Checks required files for experiment"""
    assert os.path.isdir("configs"), "configs folder is missing"
    exp_path: str = os.path.join("configs", experiment)
    assert os.path.isdir(exp_path), f"{exp_path:s} folder is missing"

    default_path: str = os.path.join(exp_path, "default.yaml")
    assert os.path.isfile(default_path), f"{default_path:s} is missing"

    config_path: str = os.path.join(exp_path, f"config.yaml")
    assert os.path.isfile(config_path), f"{config_path:s} is missing"

    file_name: str
    for file_name in os.listdir(exp_path):
        if file_name.startswith(experiment) and file_name.endswith(".yaml"):
            f_path: str = os.path.join(exp_path, file_name)
            if clean:
                os.remove(f_path)
            else:
                raise RuntimeError(f"Found this file: {f_path:s}.")

    return exp_path, config_path


def to_var_path(val: Union[str, dict]) -> List[str]:
    if isinstance(val, str):
        return [val]
    elif isinstance(val, dict):
        assert len(val) == 1
        return list(val.keys()) + to_var_path(list(val.values())[0])
    raise ValueError


def get_variables(config_data: dict) -> Tuple[Variables, Domains, BadPairs]:

    if "filter_out" in config_data:
        filter_out = config_data["filter_out"]
        del config_data["filter_out"]
    else:
        filter_out = []

    queue: List[Tuple[Union[list, dict], VarPath]] = [(config_data, [])]

    var_id: VarId = 0
    variables: Dict[VarId, VarPath] = {}
    domains: Dict[VarId, Domain] = {}

    while queue:
        node, parent = queue.pop()
        if isinstance(node, list):
            # This means @parent is a variable with multiple values
            variables[var_id] = copy(parent)
            domains[var_id] = deepcopy(node)
            var_id += 1
        elif isinstance(node, dict):
            # We go deeper
            for name, value in node.items():
                queue.append((value, parent + [name]))
        else:
            assert False, "Something went wrong with " + str(node)

    bad_pairs: BadPairs = {}
    for bad_pair in filter_out:
        vp1: VarPath = to_var_path(bad_pair["left"])
        vp2: VarPath = to_var_path(bad_pair["right"])
        pairs: List[Tuple[Any, Any]] = list(map(tuple, bad_pair["exclude"]))

        [var1_id] = [k for (k, v) in variables.items() if v[-len(vp1) :] == vp1]
        [var2_id] = [k for (k, v) in variables.items() if v[-len(vp2) :] == vp2]

        assert all(x in domains[var1_id] for (x, _) in pairs)
        assert all(y in domains[var2_id] for (_, y) in pairs)

        assert (var1_id, var2_id) not in filter_out
        assert (var1_id, var2_id) not in filter_out

        bad_pairs[(var1_id, var2_id)] = pairs

        p_str = ", ".join(list(map(lambda p: f"({p[0]}, {p[1]})", pairs)))
        v_str = f"({'.'.join(vp1):s}, {'.'.join(vp2):s})"
        print(f"Won't allow {clr(v_str, attrs=['bold']):s} from {p_str:s}.")

    return variables, domains, bad_pairs


def get_names(variables: Variables) -> Dict[VarId, str]:

    left_vars: List[VarId] = list(variables.keys())  # variables to be named
    names: Dict[VarId, str] = {}  # final names
    depth: int = 1  # how many parts to take from the path

    while left_vars:
        new_names = {j: ".".join(variables[j][-depth:]) for j in left_vars}
        left_vars = []
        for j, crt_name in new_names.items():
            if len([0 for v in new_names.values() if v == crt_name]) > 1:
                left_vars.append(j)
            else:
                names[j] = new_names[j]
        depth += 1

    return names


def check_assignment(bad_pairs: BadPairs, assignment: Assignment) -> bool:
    for (var1, var2), bad_values in bad_pairs.items():
        if (assignment[var1], assignment[var2]) in bad_values:
            return False
    return True


def prod_domains(domains: Domains, bad_pairs: BadPairs) -> Iterable[Assignment]:
    return filter(
        partial(check_assignment, bad_pairs),
        map(
            lambda a: {k: v for (k, v) in zip(domains.keys(), a)},
            product(*domains.values()),
        ),
    )


def combine_values(
    variables: Variables, values: Assignment, names: Dict[int, str]
) -> dict:
    crt_values: dict = {}
    info: List[str] = []
    for var_id, value in values.items():
        parent = crt_values
        var_path = variables[var_id]
        for key in var_path[:-1]:
            parent = parent.setdefault(key, {})
        parent[var_path[-1]] = copy(value)
        name = names[var_id].strip("_")
        if isinstance(value, dict) and "__name" in value:
            info.append(f"{name:s}={value['__name']:s}")
        else:
            info.append(f"{name:s}={value}")
    crt_values["title"] = "; ".join(info)
    return crt_values


def main():

    welcome()

    args = get_args()  # type: Namespace
    experiment = args.experiment.strip("/")  # type: str
    exp_path, config_path = check_paths(experiment, args.force or args.clean)

    if args.clean:
        print("Cleaned.")
        return

    with open(config_path) as config_file:
        config_data = yaml.load(config_file, Loader=yaml.SafeLoader)

    # BFS to get all variables

    variables, domains, bad_pairs = get_variables(config_data)
    names = get_names(variables)

    for var_id, name in names.items():
        print(
            f"{len(domains[var_id]):d} values for "
            f"{clr(name, attrs=['bold']):s}"
        )

    num = 0
    for idx, values in enumerate(prod_domains(domains, bad_pairs)):
        crt_values = combine_values(variables, values, names)
        crt_values["_experiment_parameters"] = {
            names[var_id]: value for var_id, value in values.items()
        }
        file_path = os.path.join(exp_path, f"{experiment:s}_{idx:d}.yaml")
        with open(file_path, "w") as yaml_file:
            yaml.safe_dump(crt_values, yaml_file, default_flow_style=False)
        num += 1

    print(f"{clr(f'{num:d} configurations', attrs=['bold']):s} created.")
    print("done.")

    config = get_liftoff_config()
    if not config or not config.get("no_tips", False):
        print("")
        display_tips(topic="prepare")


if __name__ == "__main__":
    main()
