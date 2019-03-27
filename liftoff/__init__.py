""" Liftoff...
"""

import yaml
from .common.dict_utils import dict_to_namespace
from .common.options_parser import OptionParser


def parse_opts():
    """ This should be called by all scripts prepared by liftoff.

        python script.py results/something/cfg.yaml

        in your script.py

          if __name__ == "__main__":
              from liftoff import parse_opts()
              main(parse_opts())
    """

    import os.path

    opt_parser = OptionParser("liftoff", ["config_path", "session_id"])
    opts = opt_parser.parse_args()
    with open(opts.config_path) as handler:
        config_data = yaml.load(handler, Loader=yaml.SafeLoader)
    opts = dict_to_namespace(config_data)
    if not hasattr(opts, "out_dir"):
        raise RuntimeError("No out_dir in config file.")
    if not os.path.isdir(opts.out_dir):  # pylint: disable=no-member
        raise RuntimeError("Out dir does not exist.")
    return opts
