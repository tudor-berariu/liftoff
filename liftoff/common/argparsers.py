from argparse import ArgumentParser, ArgumentError


def add_experiment_lookup_args(arg_parser: ArgumentParser):
    arg_parser.add_argument(
        "-e", "--experiment",
        type=str,
        dest="experiment",
        help="Find experiments by name.")
    arg_parser.add_argument(
        "-t", "--timestamp",
        type=str,
        dest="timestamp",
        help="Find experiments by timestamp.")
    arg_parser.add_argument(
        "--results-dir",
        type=str,
        dest="results_dir",
        default="results",
        help="Results directory (default: ./results)")
    arg_parser.add_argument(
        '--timestamp_fmt',
        type=str,
        dest="timestamp_fmt",
        default="%Y%b%d-%H%M%S",
        help="Default timestamp format.")


def add_experiment_args(arg_parser: ArgumentParser):
    arg_parser.add_argument(
        '-d', '--default-config-file',
        default='',
        type=str,
        dest='default_config_file',
        help='Default configuration file'
    )
    arg_parser.add_argument(
        '-c', '--config-file',
        default=["default"],
        type=str,
        nargs="+",
        dest='config_files',
        help='Configuration file.'
    )
    arg_parser.add_argument(
        '--configs-dir',
        type=str,
        default='./configs',
        dest='configs_dir',
        help='Folder to search for config files.'
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
        dest="resume",
        help="Resume some previous experiment?"
    )
    arg_parser.add_argument(
        '--out-dir',
        type=str,
        dest="out_dir"
    )
    arg_parser.add_argument(
        "--id",
        type=str,
        dest="__id"
    )


def add_launch_args(arg_parser: ArgumentParser):
    arg_parser.add_argument(
        "module",
        nargs="?",
        help="Module where to call `run(args)` from.")
    arg_parser.add_argument(
        '--runs-no',
        type=int,
        default=1,
        dest="runs_no"
    )
    arg_parser.add_argument(
        '--timestamp',
        type=str,
        dest="timestamp",
        help="Timestamp of experiment to resume.")
    arg_parser.add_argument(
        "--results-dir",
        type=str,
        dest="results_dir",
        default="results",
        help="Results directory (default: ./results)")
    arg_parser.add_argument(
        "-p", "--procs-no",
        default=4,
        type=int,
        dest="procs_no",
        help="Number of concurrent processes.")
    arg_parser.add_argument(
        "-g", "--gpus",
        default=[],
        type=int,
        nargs="*",
        dest="gpus",
        help="GPUs to distribute processes to.")
    arg_parser.add_argument(
        "--per-gpu",
        default=0,
        type=int,
        dest="per_gpu",
        help="Visible GPUs.")
    arg_parser.add_argument(
        "--no-detach",
        default=False,
        action="store_true",
        dest="no_detach",
        help="do not detach; spawn processes from python")
    arg_parser.add_argument(
        "--comment",
        type=str,
        dest="comment",
        default="",
        help="Short comment")
    arg_parser.add_argument(
        '--timestamp_fmt',
        type=str,
        dest="timestamp_fmt",
        default="%Y%b%d-%H%M%S",
        help="Default timestamp format.")