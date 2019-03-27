""" Here we define some info about liftoff that will be displayed
    in the hello message.
"""

from termcolor import colored as clr


def version():
    return "0.3"


def project_repo():
    """ TODO
    """
    return ""


def hello():
    print(
        clr(
            f"Liftoff {version():s} @ {project_repo():s}",
            attrs=["bold"],
        )
    )
