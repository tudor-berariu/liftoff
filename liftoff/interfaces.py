import sys
import os.path
from importlib import import_module
from argparse import Namespace
import urwid


"""
Fields:
 - module
 - runs-no
 - resume
 - timestamp
 - procs-no
 - gpus
 - per-gpu
 - no-detach
 - env
 - mkl
 - omp
 - comment
 - experiment
"""


def get_valid_modules():
    scripts = [f for f in os.listdir(".") if f.endswith(".py")]
    valid_modules = []
    sys.path.append(os.getcwd())
    for module_name in scripts:
        """
        try:
            module = import_module(module_name[:-3])
            if "run" in module.__dict__:
                valid_modules.append(module_name)
                del module
        except ImportError as __e:
            pass
        """
        valid_modules.append(module_name)

    return valid_modules


class LiftoffConfigurator():

    PALETTE = [("focused_item", '', 'dark gray', '', '', '#00b')]

    def __init__(self) -> None:
        options = [urwid.AttrMap(urwid.SelectableIcon(name), None, "focused_item") for name in get_valid_modules()]
        options.append(urwid.AttrMap(urwid.Edit("Other: "), None, "focused_item"))
        self.modules = modules = urwid.SimpleFocusListWalker(options)
        self.modules_box = modules_box = urwid.BoxAdapter(urwid.ListBox(modules), min(5, len(modules)))
        self.pile = pile = urwid.Pile([modules_box])
        self.fill = fill = urwid.Filler(pile, 'top')
        self.loop = urwid.MainLoop(fill, LiftoffConfigurator.PALETTE, unhandled_input=self.show_or_exit)

    def show_or_exit(self, key):
        pass

    def run(self) -> None:
        self.loop.run()

    def get_args(self) -> Namespace:
        # TODO
        return Namespace()


def configure_evolving_experiments() -> Namespace:
    uc = LiftoffConfigurator()
    uc.run()
    exit(0)
    return uc.get_args()
