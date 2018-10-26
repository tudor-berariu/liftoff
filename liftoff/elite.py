from collections import OrderedDict
from argparse import ArgumentParser, Namespace
import os
import heapq
import hashlib
import yaml
from termcolor import colored as clr
import tabulate
import numpy as np
import urwid

from liftoff.liftoff import read_genotype
from liftoff.genetics import get_mutator
from liftoff.config import dict_to_namespace
from liftoff.utils.miscellaneous import ord_dict_to_string
from liftoff.version import version


def parse_args(for_elite: bool = True) -> Namespace:
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
    if for_elite:
        arg_parser.add_argument(
            "-n", "--top", type=int, dest="top_n", default=3,
            help="Show top n individuals")
        arg_parser.add_argument(
            "-g", "--no-genotype", dest="no_genotype", default=False,
            action="store_true", help="Do not show genotypes")
        arg_parser.add_argument(
            "-i", "--individual", dest="no_average", default=False,
            action="store_true", help="Do not average over runs.")
        arg_parser.add_argument(
            "--hz", dest="horizontal", default=False,
            action="store_true", help="Show on horizontal")
    arg_parser.add_argument(
        "-m", "--meta", dest="show_meta", default=False,
        action="store_true", help="Show meta information in genotype")
    arg_parser.add_argument(
        "-p", "--path", dest="show_path", default=False,
        action="store_true", help="Show path to genotype (for copy-paste)")

    return arg_parser.parse_args()


def get_target_experiment(args: Namespace) -> str:
    exps = []
    for dirname in os.listdir(args.results_dir):
        if os.path.isdir(os.path.join(args.results_dir, dirname)):
            exps.append(dirname)

    if hasattr(args, "timestamp") and args.timestamp:
        exps = [d for d in exps if d.startswith(args.timestamp)]

    if hasattr(args, "experiment") and args.experiment:
        exps = [d for d in exps if d.endswith("_" + args.experiment)]

    if not exps:
        raise Exception("There are no experiments that match your search.")

    last_time = str(max([int(f.split("_")[0]) for f in exps]))
    exp_name = [d for d in exps if d.startswith(last_time)][0]

    return exp_name


# -----------------------------------------------------------------------------
#
# The two functions below get a path to the results folder of some
# experiment and return the best 'n' results. One averages over runs,
# while the second sorts individual runs.
#
# (liftoff 3.0)

def top_avg_experiments(exp_path: str, top_n: int = False):
    subexperiments = dict({})
    for rel_path, _, files in os.walk(exp_path):
        if ".__leaf" in files and "fitness" in files:
            with open(os.path.join(rel_path, "fitness")) as handler:
                fitness = float(handler.readline().strip())
            config_path, maybe_run_id = os.path.split(rel_path)
            try:
                run_id = int(maybe_run_id)  # This is some hardcore assumption
            except ValueError as _exception:
                run_id = -1

            if run_id < 0:
                subexperiments[rel_path] = (False, [fitness])
            else:
                runs, scores = subexperiments.setdefault(config_path, ([], []))
                runs.append(maybe_run_id)
                scores.append(fitness)

    minheap = []
    for cfg_path, (runs, scores) in subexperiments.items():
        mean, std = np.mean(scores), np.std(scores)
        if runs:
            cfg_path = os.path.join(cfg_path, runs[0])
        info = (cfg_path, mean, std, len(scores))
        if not top_n or top_n > len(minheap):
            heapq.heappush(minheap, (mean, info))
        elif mean > minheap[0][0]:
            heapq.heappushpop(minheap, (mean, info))

    lst = []
    while minheap:
        lst.append(heapq.heappop(minheap))
    lst.reverse()
    return lst


def get_top_experiments(exp_path: str, top_n: int = False):
    minheap = []

    for rel_path, _, files in os.walk(exp_path):
        if ".__leaf" in files and "fitness" in files:
            with open(os.path.join(rel_path, "fitness")) as handler:
                fitness = float(handler.readline().strip())

            if not top_n or top_n > len(minheap) or fitness > minheap[0][0]:
                heapq.heappush(minheap, (fitness, rel_path))
                if top_n and len(minheap) > top_n:
                    heapq.heappop(minheap)

    lst = []
    while minheap:
        lst.append(heapq.heappop(minheap))
    lst.reverse()
    return lst


def elite() -> None:
    args = parse_args(for_elite=True)
    exp_name = get_target_experiment(args)

    print("Experiment", clr(exp_name, "yellow", attrs=['bold']), "\n")
    exp_path = os.path.join(args.results_dir, exp_name)
    if args.no_average:
        lst = get_top_experiments(exp_path, args.top_n)
    else:
        lst = top_avg_experiments(exp_path, args.top_n)

    if args.horizontal:
        all_values = OrderedDict({})

    for (fitness, info) in lst:
        if isinstance(info, str):
            path = info
            if args.horizontal:
                all_values.setdefault("fitness", []).append(fitness)
            else:
                sfit = clr(f'{fitness:.2f}', 'white', 'on_magenta', attrs=['bold'])
                print(f"{clr('***', 'red'):s}" +
                      f" Fitness: {sfit:s}" +
                      (f" {path:s}" if args.show_path else "") +
                      f" {clr('***', 'red'):s}")
        else:
            path, _mean, std, count = info
            if args.horizontal:
                all_values.setdefault("fitness", []).append(fitness)
                all_values.setdefault("std", []).append(std)
                all_values.setdefault("runs_no", []).append(count)
            else:
                sfit = clr(f'{fitness:.2f} (std: {std:.2f})', 'white',
                           'on_magenta', attrs=['bold'])
                print(f"{clr('***', 'red'):s}" +
                      f" Fitness: {sfit:s}" +
                      (f" {path:s}" if args.show_path else "") +
                      f" {clr('***', 'red'):s}")

        if args.no_genotype:
            continue

        ph_path = os.path.join(path, "phenotype.yaml")
        cfg_path = os.path.join(path, "cfg.yaml")

        if os.path.isfile(ph_path):
            with open(ph_path) as handler:
                data = yaml.load(handler, Loader=yaml.SafeLoader)
            if not args.show_meta:
                if "meta" in data:
                    del data["meta"]
        elif os.path.isfile(cfg_path):
            with open(cfg_path) as handler:
                all_data = yaml.load(handler, Loader=yaml.SafeLoader)
            data = all_data["experiment_parameters"]
            if args.no_average:
                data["run_id"] = all_data["run_id"]
        else:
            continue

        queue = [("", data)]
        pairs = []

        while queue:
            prev, obj = queue.pop(0)
            if isinstance(obj, dict):
                for key, value in obj.items():
                    queue.append((((prev + ".") if prev else "") + key, value))
            else:
                pairs.append((prev, obj))
        pairs.sort(key=lambda x: x[0])

        if args.horizontal:
            for (name, value) in pairs:
                all_values.setdefault(name, []).append(value)
        else:
            print(tabulate.tabulate(pairs))
            print("\n")

    if args.horizontal:
        print(tabulate.tabulate(all_values, headers="keys"))
        print("\n")


def manual_add() -> None:
    args = parse_args(for_elite=True)
    exp_name = get_target_experiment(args)
    exp_path = os.path.join(args.results_dir, exp_name)
    genotype_cfg_path = os.path.join(exp_path, "genotype.yaml")
    genotype_cfg = read_genotype(genotype_cfg_path)
    mutator = get_mutator(genotype_cfg)

    lst = get_top_experiments(exp_path, args.top_n)

    if not lst:
        print("Experiment", clr(exp_name, "yellow"), "has nothing yet.")
        return

    nexperiments = len(lst)
    crt_idx = 0

    # -- urwid stuff

    palette = [
        ("banner", "black", "dark red"),
        ("title", "black", "light gray"),
        ("info", "white", "dark blue"),
        ("error_text", 'dark red', 'light gray'),
        ('edit_focus', '', 'dark gray', '', '', '#00b'),
        ('button_focus', '', 'dark gray', '', '', '#00f'),
        ("ok", "dark green", ""),
        ("notok", 'dark red', ''),
        ("normal", '', '')
    ]

    standard_msg = "Press 'a'/'d' to change file; 'r' to refresh; 'c' to check, 's' to save; 'q' to quit."

    title = urwid.Text(('title', "Liftoff v" + version()), align='center')
    title_map = urwid.AttrMap(title, "banner")
    experiment = urwid.Text(('title', "Experiment: " + exp_name), align='center')
    experiment_map = urwid.AttrMap(experiment, "banner")
    info = urwid.Text(("info", f"File {crt_idx:d}/{nexperiments:d} | "
                       f"Fitness: {lst[crt_idx][0]:.3f}"), align="center")
    infomap = urwid.AttrMap(info, "info")

    prev_button = urwid.Button("previous")
    prev_map = urwid.AttrMap(prev_button, "None", "button_focus")
    next_button = urwid.Button("next")
    next_map = urwid.AttrMap(next_button, "None", "button_focus")

    header = urwid.Columns([prev_map, infomap, next_map])

    original_keys = urwid.Text("")
    original_values = urwid.Text("")
    new_values = urwid.SimpleFocusListWalker([urwid.Text("nothing")])
    new_values_lb = urwid.BoxAdapter(urwid.ListBox(new_values), 10)

    files = urwid.Columns([original_keys, original_values, new_values_lb])

    msg = urwid.Text("")
    msg_map = urwid.AttrMap(msg, None)

    areyousure = urwid.Button("Save new genotype!")
    areyousure_map = urwid.AttrMap(areyousure, "None", "button_focus")
    revert = urwid.Button("Refresh")
    revert_map = urwid.AttrMap(revert, "None", "button_focus")
    check = urwid.Button("Check")
    check_map = urwid.AttrMap(check, "None", "button_focus")
    buttons = urwid.Columns([revert_map, areyousure_map, check_map])
    edit_to_attrmap = {}

    for bttn in [prev_button, next_button, revert, check, areyousure]:
        bttn._label.align = "center"

    pile = urwid.Pile([title_map, experiment_map, header, urwid.Divider(), files, urwid.Divider(),
                       msg_map, urwid.Divider(), buttons])

    new_items = OrderedDict({})
    default_values = {}

    press_again = True

    def save_file(_button):
        nonlocal press_again

        try:
            genotype = yaml.load("\n".join([f"{key:s}: {e.edit_text}" for (key, e) in new_items.items()]),
                                 Loader=yaml.SafeLoader)
            genotype_nm = dict_to_namespace(genotype)
            mutator.check_genotype(genotype_nm)

            if press_again:
                msg.set_text("Please press 'Save' again if you are sure!")
                msg_map.set_attr_map({None: 'ok'})
                press_again = False
                return

            title = ord_dict_to_string(genotype, ignore="meta")
            if len(title) > 200:
                title = hashlib.md5(title.encode('utf-8')).hexdigest()

            if not os.path.isdir(os.path.join(exp_path, "to_run")):
                os.makedirs(os.path.join(exp_path, "to_run"))

            genotype_path = os.path.join(exp_path, "to_run", title + ".yaml")
            with open(genotype_path, "w") as yaml_file:
                yaml.safe_dump(genotype, yaml_file, default_flow_style=False)
            msg.set_text("Saved to " + genotype_path)
            msg_map.set_attr_map({None: 'ok'})
            press_again = True

        except Exception as e:
            msg.set_text(str(e))
            msg_map.set_attr_map({None: 'notok'})

    def undo_settings(_button):
        refresh()

    def check_values(_button):
        nonlocal press_again
        press_again = True

        try:
            data = yaml.load("\n".join([f"{key:s}: {e.edit_text}" for (key, e) in new_items.items()]),
                             Loader=yaml.SafeLoader)
            nms_data = dict_to_namespace(data)
            mutator.check_genotype(nms_data)
            msg.set_text("Ok!")
            msg_map.set_attr_map({None: 'ok'})

        except Exception as e:
            msg.set_text(str(e))
            msg_map.set_attr_map({None: 'notok'})

    def move_to_prev(_button):
        nonlocal crt_idx
        crt_idx = max(0, crt_idx - 1)
        refresh()

    def move_to_next(_button):
        nonlocal crt_idx
        crt_idx = min(nexperiments - 1, crt_idx + 1)
        refresh()

    def changed_text(edit_widget, _text: str) -> None:
        nonlocal press_again
        press_again = True
        if default_values[edit_widget] != edit_widget.edit_text:
            edit_to_attrmap[edit_widget].set_attr_map({None: 'notok'})
        else:
            edit_to_attrmap[edit_widget].set_attr_map({None: ''})

    def refresh():
        nonlocal press_again
        info.set_text(f"File {crt_idx + 1:d}/{nexperiments:d} | " +
                      f"Fitness: {lst[crt_idx][0]:.3f}")
        genotype = read_genotype(os.path.join(lst[crt_idx][1], "genotype.yaml"))
        if hasattr(genotype, "meta"):
            delattr(genotype, "meta")

        original_keys.set_text("\n".join(map(str, genotype.__dict__.keys())))
        original_values.set_text("\n".join(map(str, genotype.__dict__.values())))
        new_values_lb.height = len(genotype.__dict__)
        new_values.clear()
        new_items.clear()
        default_values.clear()
        for edit_widget in edit_to_attrmap.keys():
            urwid.disconnect_signal(edit_widget, "postchange", changed_text)
        edit_to_attrmap.clear()
        for key, value in genotype.__dict__.items():
            new_edit = urwid.Edit(u"")
            new_items[key] = new_edit
            default_values[new_edit] = str(value)
            new_edit.set_edit_text(str(value))
            edit_to_attrmap[new_edit] = new_attr_map = urwid.AttrMap(new_edit, None, "edit_focus")
            new_values.append(new_attr_map)
            urwid.connect_signal(new_edit, "postchange", changed_text)
        msg.set_text(standard_msg)
        msg_map.set_attr_map({None: 'normal'})
        press_again = True
    refresh()

    focus_order = [(header, prev_map),
                   (header, next_map),
                   (files, new_values_lb),
                   (buttons, revert_map),
                   (buttons, areyousure_map),
                   (buttons, check_map)]

    def set_next_focus():
        focused_widgets = pile.get_focus_widgets()
        for idx, (_, widget) in enumerate(focus_order):
            if widget in focused_widgets:
                break
        idx = (idx + 1) % len(focus_order)
        parent, widget = focus_order[idx]
        pile.set_focus(parent)
        parent.set_focus(widget)

    def show_or_exit(key):
        nonlocal crt_idx
        if key in ["q", "Q"]:
            raise urwid.ExitMainLoop()
        elif key in ["a", "A"]:
            crt_idx = max(0, crt_idx - 1)
            refresh()
        elif key in ["d", "D"]:
            crt_idx = min(nexperiments - 1, crt_idx + 1)
            refresh()
        elif key in ["r", "R"]:
            refresh()
        elif key in ["c", "C"]:
            check_values(None)
        elif key in ["s", "S"]:
            save_file(None)
        elif key in ["tab"]:
            set_next_focus()

    urwid.connect_signal(areyousure, "click", save_file)
    urwid.connect_signal(revert, "click", undo_settings)
    urwid.connect_signal(check, "click", check_values)
    urwid.connect_signal(next_button, "click", move_to_next)
    urwid.connect_signal(prev_button, "click", move_to_prev)

    fill = urwid.Filler(pile, 'top')
    loop = urwid.MainLoop(fill, palette, unhandled_input=show_or_exit)
    loop.run()
