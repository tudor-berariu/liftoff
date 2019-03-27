""" Here we define wrapper functions to be called when one invokes
    console commands.
"""


def prepare():
    """ liftoff-prepare
    """
    from .common.local_info import hello
    from .prepare import prepare as _prepare

    hello()
    _prepare()


def liftoff():
    """ liftoff-prepare
    """
    from .common.local_info import hello
    from .liftoff import launch as _liftoff

    hello()
    _liftoff()


def clean():
    """ liftoff-clean
    """
    from .common.local_info import hello
    from .sanitizer import clean as _clean

    hello()
    _clean()


def abort():
    """ liftoff-abort
    """
    from .common.local_info import hello
    from .abort import abort as _abort

    hello()
    _abort()


def procs():
    """ liftoff-procs
    """
    from .common.local_info import hello
    from .proc_info import procs as _procs

    hello()
    _procs()


def status():
    """ liftoff-status
    """
    from .common.local_info import hello
    from .status import status as _status

    hello()
    _status()
