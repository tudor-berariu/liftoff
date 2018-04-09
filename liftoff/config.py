from argparse import Namespace
from typing import List, Union
from termcolor import colored as clr


def namespace_to_dict(namespace: Namespace) -> dict:
    """Deep (recursive) transform from Namespace to dict"""
    dct = {}
    for key, value in namespace.__dict__.items():
        if isinstance(value, Namespace):
            dct[key] = namespace_to_dict(value)
        else:
            dct[key] = value
    return dct


def dict_to_namespace(dct: dict) -> Namespace:
    """Deep (recursive) transform from Namespace to dict"""
    namespace = Namespace()
    for key, value in dct.items():
        name = key.rstrip("_")
        if isinstance(value, dict) and not key.endswith("_"):
            setattr(namespace, name, dict_to_namespace(value))
        else:
            setattr(namespace, name, value)
    return namespace


def value_of(cfg: Namespace, name: str, default=None) -> object:
    return getattr(cfg, name) if hasattr(cfg, name) else default


def _update_config(default_cfg: Namespace, diff_cfg: Namespace):
    """Updates @default_cfg with values from @diff_cfg"""

    for key, value in diff_cfg.__dict__.items():
        if isinstance(value, Namespace):
            if hasattr(default_cfg, key):
                _update_config(getattr(default_cfg, key), value)
            else:
                setattr(default_cfg, key, value)
        else:
            setattr(default_cfg, key, value)


def config_to_string(cfg: Namespace, indent: int = 0) -> str:
    """Creates a multi-line string with the contents of @cfg."""

    text = ""
    for key, value in cfg.__dict__.items():
        text += " " * indent + clr(key, "yellow") + ": "
        if isinstance(value, Namespace):
            text += "\n" + config_to_string(value, indent + 2)
        else:
            text += clr(str(value), "red") + "\n"
    return text


def parse_args(strict: bool = True) -> Namespace:
    import argparse

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        '-d', '--default_config_fle',
        default='default',
        dest='default_config_file',
        help='Default configuration file'
    )
    arg_parser.add_argument(
        '-c', '--config_file',
        default=['default'],
        nargs="+",
        dest='config_files',
        help='Configuration file.'
    )
    arg_parser.add_argument(
        '-e', '--experiment',
        type=str,
        default="",
        dest="experiment",
        help="Experiment. Overrides cf and dcf"
    )
    arg_parser.add_argument(
        '--resume',
        default=False,
        action="store_true",
        dest="resume"
    )
    arg_parser.add_argument(
        '--runs-no',
        default=1,
        type=int,
        dest="runs_no"
    )
    if strict:
        return arg_parser.parse_args()
    return arg_parser.parse_known_args()[0]


def read_config(strict: bool = False) -> Union[Namespace, List[Namespace]]:
    """Reads an YAML config file and transforms it to a Namespace

    # 1st use (when --config_file and --default_config_file are provided)

    It reads two config files and combines their info into a
    `Namespace`. One is supposed to be the default configuration with
    the common settings for most experiments, while the other
    specifies what changes. The YAML structure is transformed into a
    Namespace excepting keys ending with '_'. The reason for this
    behaviour is the following: sometimes you want to overwrite a full
    dictionary, not just specific values (e.g. args for optimizer).

    # 2nd use (when --experiment is provided)

    There must be a folder with the experiment name in ./configs/ and
    there several YAMLs:
      - ./configs/<experiment_name>/default.yaml
      - ./configs/<experiment_name>/<experiment_name>_[...].yaml

    Each of those files is combined with default exactly as above. A
    list of `Namespace`s is returned.

    """
    import yaml
    import os.path

    args = parse_args(strict=strict)

    print(args)

    if args.experiment:
        from os import listdir
        path = f"./configs/{args.experiment:s}/"
        config_files = [f for f in listdir(path)
                        if f.startswith(args.experiment + "_")
                        and f.endswith(".yaml")]
        default_config_file = "default.yaml"
        print(f"Found {len(config_files):d} configs in current experiment!")
    else:
        path = f"./configs/"
        config_files = [f + ".yaml" for f in args.config_files]
        default_config_file = args.default_config_file + ".yaml"

    cfgs = []
    for config_file in config_files:
        with open(os.path.join(path, config_file)) as handler:
            config_data = yaml.load(handler, Loader=yaml.SafeLoader)
        cfg = dict_to_namespace(config_data)

        if default_config_file != config_file:
            with open(os.path.join(path, default_config_file)) as handler:
                default_cfg_data = yaml.load(handler, Loader=yaml.SafeLoader)
            default_cfg = dict_to_namespace(default_cfg_data)
            _update_config(default_cfg, cfg)
            cfg = default_cfg

        # Make sure experiment / title / resume / runs_no are set

        if not hasattr(cfg, "experiment"):
            if args.experiment:
                cfg.experiment = args.experiment
            else:
                cfg.experiment = args.default_config_file
        if not hasattr(cfg, "title"):
            cfg.title = config_file[:-5]  # lose .yaml

        cfg.resume = args.resume
        if not hasattr(cfg, "runs_no"):
            cfg.runs_no = args.runs_no

        cfgs.append(cfg)

        if value_of(cfg, 'verbose', 0) > 0:
            import sys
            sys.stdout.write(f"{clr('[Config]', 'red'):s} ")
            if default_config_file != config_file:
                print(f"Read {config_file:s} over {default_config_file:s}.")
            else:
                print(f"Read {config_file:s}.")

    assert len(set([cfg.experiment for cfg in cfgs])) == 1, \
        "All configs must be part of the same experiment"

    return cfgs[0] if len(cfgs) == 1 else cfgs
