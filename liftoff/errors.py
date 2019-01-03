import os
import os.path
from argparse import ArgumentParser, Namespace
import hashlib
import urwid
import locale
locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
import yaml

from .version import version
from .config import config_to_string, dict_to_namespace
from .common.argparsers import add_experiment_lookup_args
from .common.lookup import get_latest_experiment


def parse_args() -> Namespace:
    arg_parser = ArgumentParser()
    add_experiment_lookup_args(arg_parser)
    return arg_parser.parse_args()


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


PALLETTE = [
    ("banner", "black", "dark red"),
    ("title", "black", "light gray"),
    ("info", "white", "dark blue"),
    ("error_text", 'dark red', 'light gray')
]


def main():
    args = parse_args()
    exp_name, exp_path = get_latest_experiment(**args.__dict__)
    errors, all_files = get_errors(exp_path)
    nerrors = len(errors)
    if not errors:
        print("There are no errors in", exp_name)
        return

    crt_err_idx = 0
    crt_file_idx = 0
    crt_details = all_files[errors[crt_err_idx][0]][crt_file_idx][1]
    nfiles = len(all_files[errors[crt_err_idx][0]])

    title = urwid.Text(('title', "Liftoff v" + version()), align='center')
    title_map = urwid.AttrMap(title, "banner")
    experiment = urwid.Text("Experiment: " + exp_name, align='center')
    experiment_map = urwid.AttrMap(experiment, "title")

    stats = urwid.Text(f"Error {(crt_err_idx + 1):d}/{nerrors:d} | "
                       f"File {(crt_file_idx + 1):d}/{nfiles:d} | "
                       "Press w/s to change errors, and a/d to change files.")
    stats_map = urwid.AttrMap(stats, "info")
    err_text = urwid.Text(errors[crt_err_idx][1])
    err_map = urwid.AttrMap(err_text, "error_text")
    details_text = urwid.Text(config_to_string(
        dict_to_namespace(crt_details), color=False))
    pile = urwid.Pile([title_map, experiment_map, stats_map,
                       urwid.Divider(),
                       err_map,
                       urwid.Divider(),
                       details_text])

    def refresh():
        nonlocal crt_err_idx, crt_file_idx, crt_details
        nonlocal nfiles, nerrors, all_files
        crt_details = all_files[errors[crt_err_idx][0]][crt_file_idx][1]
        nfiles = len(all_files[errors[crt_err_idx][0]])
        stats.set_text(f"Error {(crt_err_idx + 1):d}/{nerrors:d} | "
                       f"File {(crt_file_idx + 1):d}/{nfiles:d} | "
                       "Press w/s to change errors, and a/d to change files.")
        err_text.set_text(errors[crt_err_idx][1])
        details_text.set_text(config_to_string(
            dict_to_namespace(crt_details), color=False))

    def show_or_exit(key):
        nonlocal crt_err_idx, crt_file_idx, nfiles, nerrors

        if key in ["q", "Q"]:
            raise urwid.ExitMainLoop()
        if key in ["a"] and crt_file_idx > 0:
            crt_file_idx -= 1
            refresh()
        elif key in ["d"] and crt_file_idx < nfiles - 1:
            crt_file_idx += 1
            refresh()
        elif key in ["w"] and crt_err_idx > 0:
            crt_err_idx -= 1
            crt_file_idx = 0
            refresh()
        elif key in ["s"] and crt_err_idx < nerrors - 1:
            crt_err_idx += 1
            crt_file_idx = 0
            refresh()

    fill = urwid.Filler(pile, 'top')
    loop = urwid.MainLoop(fill, PALLETTE, unhandled_input=show_or_exit)
    loop.run()
