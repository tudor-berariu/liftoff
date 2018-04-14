from copy import copy, deepcopy
import itertools
from argparse import ArgumentParser, Namespace
from typing import List, Tuple
import os.path
import yaml
from termcolor import colored as clr


def get_args() -> Namespace:
    arg_parser = ArgumentParser("Prepare experiment for liftoff")
    arg_parser.add_argument("experiment", type=str,
                            help="Experiment to prepare")
    arg_parser.add_argument("-f", "--force", action="store_true",
                            default=False, dest="force",
                            help="Delete other generated files if found.")
    arg_parser.add_argument("-c", "--clean", action="store_true",
                            default=False, dest="clean",
                            help="Deletes generated files if found.")

    return arg_parser.parse_args()


def get_paths(experiment: str, clean: bool = False) -> Tuple[str, str]:
    assert os.path.isdir('configs'), "configs folder is missing"
    exp_path = os.path.join('configs', experiment)
    assert os.path.isdir(exp_path), f"{exp_path:s} folder is missing"

    default_path = os.path.join(exp_path, 'default.yaml')
    assert os.path.isfile(default_path), f"{default_path:s} is missing"

    config_path = os.path.join(exp_path, f"config.yaml")
    assert os.path.isfile(config_path), f"{config_path:s} is missing"

    for file_name in os.listdir(exp_path):
        if file_name.startswith(experiment) and file_name.endswith(".yaml"):
            if clean:
                os.remove(os.path.join(exp_path, file_name))
            else:
                assert False,\
                    "Found this file: {os.path.join(exp_path, f)}:s."

    return exp_path, config_path


def get_variables(config_data)-> Tuple[List[List[str]], List[List[object]]]:

    queue = [(config_data, [])]
    variables, domains = [], []

    while queue:
        node, parent = queue.pop()
        if isinstance(node, list):
            # This means @parent is a variable wit multiple values
            variables.append(copy(parent))
            domains.append(deepcopy(node))
        elif isinstance(node, dict):
            # We go deeper
            for name, value in node.items():
                queue.append((value, parent + [name]))
        else:
            assert False, "Something went wrong with " + str(node)

    return variables, domains


def get_names(variables: List[List[str]]) -> List[str]:

    left_vars = list(range(len(variables)))
    names = [None] * len(variables)
    depth = 1

    while left_vars:
        _names = [":".join(variables[j][-depth:]) for j in left_vars]
        _left_vars = []
        for i, idx in enumerate(left_vars):
            if _names[i] in _names[:i] + _names[(i + 1):]:
                left_vars.append(idx)
            else:
                names[idx] = _names[i]

        left_vars, depth = _left_vars, depth + 1
    return variables


def combine_values(variables: List[List[str]],
                   values: List[object],
                   names: List[str]) -> dict:
    crt_values = {}
    info = []
    for keys, value, name in zip(variables, values, names):
        parent = crt_values
        for key in keys[:-1]:
            parent = parent.setdefault(key, {})
        parent[keys[-1]] = copy(value)
        info.append(f"{'.'.join(name):s}={value}")
    crt_values["title"] = "; ".join(info)
    return crt_values


def main():
    args = get_args()
    experiment = args.experiment
    exp_path, config_path = get_paths(experiment, args.force or args.clean)

    if args.clean:
        print("Cleaned.")
        return

    with open(config_path) as config_file:
        config_data = yaml.load(config_file, Loader=yaml.SafeLoader)

    # BFS to get all variables

    variables, domains = get_variables(config_data)
    names = get_names(variables)

    for name, domain in zip(names, domains):
        print(f"{len(domain):d} values for "
              f"{clr('.'.join(name), attrs=['bold']):s}")

    for idx, values in enumerate(itertools.product(*domains)):
        crt_values = combine_values(variables, values, names)
        file_path = os.path.join(exp_path, f"{experiment:s}_{idx:d}.yaml")
        with open(file_path, "w") as yaml_file:
            yaml.safe_dump(crt_values, yaml_file, default_flow_style=False)
    print("done.")


if __name__ == "__main__":
    main()
