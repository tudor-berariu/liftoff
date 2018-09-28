import urwid
import os
import os.path
from argparse import ArgumentParser, Namespace
import hashlib
import yaml

from liftoff.version import version
from liftoff.config import config_to_string, dict_to_namespace


def parse_args() -> Namespace:
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


def find_experiment():
    args = parse_args()

    candidate_exps = []
    for dirname in os.listdir(args.results_dir):
        if os.path.isdir(os.path.join(args.results_dir, dirname)):
            candidate_exps.append(dirname)

    if hasattr(args, "timestamp") and args.timestamp:
        candidate_exps = [d for d in candidate_exps if d.startswith(args.timestamp)]

    if hasattr(args, "experiment") and args.experiment:
        candidate_exps = [d for d in candidate_exps if d.endswith("_" + args.experiment)]

    assert candidate_exps

    last_time = str(max([int(f.split("_")[0]) for f in candidate_exps]))
    exp_name = [d for d in candidate_exps if d.startswith(last_time)][0]
    return exp_name, os.path.join(args.results_dir, exp_name)


def get_errors(experiment_path):
    unique_errors = {}
    all_files = {}
    for rel_path, _, files in os.walk(experiment_path):
        if ".__crash" in files and "err" in files:
            with open(os.path.join(rel_path, "err"), 'r') as handler:
                err = handler.read()
                md5sum = hashlib.md5(err.encode('utf-8')).hexdigest()
            if "phenotype.yaml" in files:
                with open(os.path.join(rel_path, "phenotype.yaml")) as handler:
                    details = yaml.load(handler, Loader=yaml.SafeLoader)
            elif "cfg.yaml" in files:
                with open(os.path.join(rel_path, "cfg.yaml")) as handler:
                    details = yaml.load(handler, Loader=yaml.SafeLoader)
            else:
                details = {}
            unique_errors[md5sum] = err
            all_files.setdefault(md5sum, []).append((rel_path, details))

    return [(key, value) for (key, value) in unique_errors.items()], all_files


palette = [
    ("banner", "black", "dark red"),
    ("title", "black", "light gray"),
    ("info", "white", "dark blue"),
    ("error_text", 'dark red', 'light gray')
]


def main():
    exp_name, exp_path = find_experiment()
    errors, all_files = get_errors(exp_path)
    if not errors:
        print("There are no errors in", exp_name)
        return

    crt_err_idx = 0
    crt_md5sum, crt_err = errors[crt_err_idx]
    crt_file_idx = 0
    crt_details = all_files[crt_md5sum][crt_file_idx][1]

    title = urwid.Text(('title', "Liftoff v" + version()), align='center')
    title_map = urwid.AttrMap(title, "banner")
    experiment = urwid.Text("Experiment: " + exp_name, align='center')
    experiment_map = urwid.AttrMap(experiment, "title")

    stats = urwid.Text(f"Error {(crt_err_idx + 1):d}/{len(errors):d} | "
                       f"File {(crt_file_idx + 1):d}/{len(all_files[crt_md5sum]):d} | "
                       "Press w/s to change errors, and a/d to change files.")
    stats_map = urwid.AttrMap(stats, "info")
    err_text = urwid.Text(crt_err)
    err_map = urwid.AttrMap(err_text, "error_text")
    details_text = urwid.Text(config_to_string(dict_to_namespace(crt_details), color=False))
    div = urwid.Divider()
    pile = urwid.Pile([title_map, experiment_map,
                       stats_map, div, err_map, div, details_text])

    def refresh():
        nonlocal crt_err_idx, crt_file_idx, crt_md5sum, crt_err, crt_details, all_files
        crt_md5sum, crt_err = errors[crt_err_idx]
        crt_details = all_files[crt_md5sum][crt_file_idx][1]
        stats.set_text(f"Error {(crt_err_idx + 1):d}/{len(errors):d} | "
                       f"File {(crt_file_idx + 1):d}/{len(all_files[crt_md5sum]):d} | "
                       "Press w/s to change errors, and a/d to change files.")
        err_text.set_text(crt_err)
        details_text.set_text(config_to_string(dict_to_namespace(crt_details), color=False))

    def show_or_exit(key):
        nonlocal crt_err_idx, crt_file_idx, crt_md5sum, all_files, errors

        if key in ["q", "Q"]:
            raise urwid.ExitMainLoop()
        if key in ["a"] and crt_file_idx > 0:
            crt_file_idx -= 1
            refresh()
        elif key in ["d"] and crt_file_idx < len(all_files[crt_md5sum]) - 1:
            crt_file_idx += 1
            refresh()
        elif key in ["w"] and crt_err_idx > 0:
            crt_err_idx -= 1
            crt_file_idx = 0
            refresh()
        elif key in ["s"] and crt_err_idx < len(errors) - 1:
            crt_err_idx += 1
            crt_file_idx = 0
            refresh()

    fill = urwid.Filler(pile, 'top')
    loop = urwid.MainLoop(fill, palette, unhandled_input=show_or_exit)
    loop.run()
