""" In order to reuse and have a consistent set of arguments we use the
    functions in this file to build argument parsers for all scripts.

    TODO: change to class methods to common methods if there is no need to call
        those functions outside an instance of OptionParser.
"""
import os
from argparse import ArgumentParser, Namespace
from typing import List
import uuid

from .liftoff_config import LiftoffConfig


class OptionParser:
    """ This class facilitates combining command line arguments and liftoff
        settings.
    """

    def __init__(self, name, arguments: List[str]) -> None:
        self.liftoff_config = LiftoffConfig()
        self.arg_parser = ArgumentParser(name)
        self.arguments = [str(arg) for arg in arguments]

        for arg in self.arguments:
            getattr(self, f"_add_{arg:s}")()

    def parse_args(self, args: List[str] = None, strict: bool = True) -> Namespace:
        """ Parses command-line arguments and completes options with values
            from liftoff configuration files.
        """

        if strict:
            opts = self.arg_parser.parse_args(args=args)
        else:
            opts = self.arg_parser.parse_known_args(args=args)

        for arg in self.arguments:
            if not hasattr(opts, arg) or getattr(opts, arg) is None:
                setattr(opts, arg, self.liftoff_config.get(arg))

        if hasattr(opts, "verbose") and isinstance(opts.verbose, list):
            opts.verbose = len(opts.verbose)

        opts.session_id = str(uuid.uuid4())

        return opts

    def _add_all(self) -> None:
        self.arg_parser.add_argument(
            "-a",
            "--all",
            action="store_true",
            dest="all",
            help="Target all experiments not just the latest.",
        )

    def _add_append_to(self) -> None:
        self.arg_parser.add_argument(
            "--append-to",
            dest="append_to",
            required=False,
            type=str,
            help="Append files to some existing experiment.",
        )

    def _add_args(self) -> None:
        self.arg_parser.add_argument(
            "--args",
            dest="args",
            type=str,
            nargs="*",
            help="""List of `key=value` strings that overwrite the config file.\
                Example: `--args model.name=AlexNet` will overwrite the value\
                for `model.name` in the config file.""",
        )

    def _add_copy_to_clipboard(self) -> None:
        self.arg_parser.add_argument(
            "--cc",
            action="store_true",
            dest="copy_to_clipboard",
            help="Copy experiment path to clipboard",
        )

    def _add_config_path(self) -> None:
        self.arg_parser.add_argument(
            "config_path", type=str, help="Give a specific name to the experiment."
        )

    def _add_do(self) -> None:
        self.arg_parser.add_argument(
            "--do",
            action="store_true",
            dest="do",
            help="Apply the actions (do not only simulate).",
        )

    def _add_crashed_only(self) -> None:
        self.arg_parser.add_argument(
            "--crashed-only",
            action="store_true",
            dest="crashed_only",
            help="Apply the actions only to crashed experiment runs.",
        )

    def _add_experiment(self) -> None:
        self.arg_parser.add_argument(
            "experiment",
            nargs="?",
            type=str,
            help="Give a specific name to the experiment.",
        )

    def _add_filters(self) -> None:
        self.arg_parser.add_argument(
            "--filters",
            dest="filters",
            type=str,
            nargs="*",
            help="""List of `key=value` strings present in your config files \
            or results folder that you wish to filter.\
            Example: `--filters optim.lr=0.001 model.name=AlexNet` will match \
            experiments containing this configuration. `liftoff ...` will use it to \
            leave out matched experiments from launching. `liftoff-lock/unlock` will \
            use it to act on matched experiments accordingly.""",
        )

    def _add_gpus(self) -> None:
        self.arg_parser.add_argument(
            "--gpus",
            dest="gpus",
            nargs="*",
            default=[],
            help="List of available GPUs. Eg.: --gpus 0 1",
        )

    def _add_name(self) -> None:
        self.arg_parser.add_argument(
            "--name",
            dest="name",
            required=False,
            type=str,
            help="Give a specific name to the experiment.",
        )

    def _add_optimize(self) -> None:
        self.arg_parser.add_argument(
            "-O",
            action="store_true",
            dest="optimize",
            help="Send -OO to python process.",
        )

    def _add_overwrite(self) -> None:
        self.arg_parser.add_argument(
            "--overwrite",
            action="store_true",
            dest="overwrite",
            help="Overwrite files if you find them (not if .__end is there",
        )

    def _add_no_detach(self) -> None:
        self.arg_parser.add_argument(
            "--no-detach",
            action="store_true",
            dest="no_detach",
            help="Do not detach the process with nohup.",
        )

    def _add_per_gpu(self) -> None:
        self.arg_parser.add_argument(
            "--per-gpu",
            dest="per_gpu",
            nargs="*",
            type=int,
            default=[],
            help="Max number of experiment runs to load on each GPU.",
        )

    def _add_pid(self) -> None:
        self.arg_parser.add_argument("pid", type=int, help="PID of liftoff to kill.")

    def _add_procs_no(self) -> None:
        default_value = self.liftoff_config.get("procs_no")
        if default_value is None:
            default_value = 1
        default_value = int(default_value)
        self.arg_parser.add_argument(
            "--procs-no",
            dest="procs_no",
            required=False,
            type=int,
            default=default_value,
            help="""Total number of experiment runs allowed to run concurrently.\
            Defaults to 1.""",
        )

    def _add_results_path(self) -> None:
        default_value = self.liftoff_config.get("results_path")
        if default_value is None:
            default_value = os.path.join(".", "results")
        default_value = str(default_value)
        self.arg_parser.add_argument(
            "--results-path",
            dest="results_path",
            required=False,
            type=str,
            default=default_value,
            help="Root path containing experiments. Defaults to `./results`.",
        )

    def _add_runs_no(self) -> None:
        default_value = self.liftoff_config.get("runs_no")
        if default_value is None:
            default_value = 1
        default_value = int(default_value)
        self.arg_parser.add_argument(
            "--runs-no",
            dest="runs_no",
            required=False,
            type=int,
            default=default_value,
            help="Number of runs for each sub-experiment",
        )

    def _add_runs(self) -> None:
        self.arg_parser.add_argument(
            "--runs",
            dest="runs",
            required=True,
            type=int,
            nargs="+",
            help="Runs we refer to here.",
        )

    def _add_safe(self) -> None:
        self.arg_parser.add_argument(
            "--safe",
            action="store_true",
            dest="safe",
            help="Do not clean ended, but locked ones.",
        )

    def _add_script(self) -> None:
        self.arg_parser.add_argument(
            "script", type=str, help="Script to be executed with all those configs."
        )

    def _add_clean_all(self) -> None:
        self.arg_parser.add_argument(
            "--clean-all",
            action="store_true",
            dest="clean_all",
            help="Clean *all* the files an experiment run produced.",
        )

    def _add_timestamp_fmt(self) -> None:
        default_value = self.liftoff_config.get("timestamp_fmt")
        if default_value is None:
            default_value = "%Y%b%d-%H%M%S"
        default_value = str(default_value)

        self.arg_parser.add_argument(
            "--timestamp-fmt",
            type=str,
            dest="timestamp_fmt",
            default=default_value,
            help="Timestamp format to be used.",
        )

    def _add_verbose(self) -> None:
        self.arg_parser.add_argument(
            "-v",
            const=1,
            dest="verbose",
            action="append_const",
            help="Verbose level (default: 0) e.g. -v / -vv / -vvv",
        )

    def _add_session_id(self) -> None:
        self.arg_parser.add_argument(
            "--session-id",
            type=str,
            dest="session_id",
            required=True,
            help="Seesion id (needed to identify process by command).",
        )

    def _add_time_limit(self) -> None:
        self.arg_parser.add_argument(
            "--time-limit",
            type=int,
            dest="time_limit",
            default=0,
            help="Stop if this time limit (in miuntes) is exceeded.",
        )

    def _add_start_by(self) -> None:
        self.arg_parser.add_argument(
            "--start-by",
            type=int,
            dest="start_by",
            default=0,
            help="Do not launch processes if this time (in seconds) has been exceeded.",
        )

    def _add_end_by(self) -> None:
        self.arg_parser.add_argument(
            "--end-by",
            type=int,
            dest="end_by",
            default=0,
            help="Pass this to the processes using ENDBY variable.",
        )

    def _add_max_runs(self) -> None:
        self.arg_parser.add_argument(
            "--max-runs",
            type=int,
            dest="max_runs",
            default=0,
            help="Stop if max runs have been exceeded. (default 0 - run all).",
        )

    def _add_shuffle(self) -> None:
        self.arg_parser.add_argument(
            "--shuffle",
            action="store_true",
            dest="shuffle",
            help="Makes sure the runs are launched randomly.",
        )
