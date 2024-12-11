""" Here we define some info about liftoff that will be displayed
    in the hello message.
"""

import os.path
import git
from termcolor import colored as clr


def version():
    """Q: Is there a better way to have some unique source for the version?
    A: Yes. 
    Proposal: Use poetry instead of setup.py, will solve this too.
    """
    from ..version import __version__ as version

    return version


def get_branch_commit(path: str):
    try:
        repo = git.Repo(path=path, search_parent_directories=True)
        return (repo.active_branch.name, repo.head.object.hexsha[-7:])
    except git.InvalidGitRepositoryError:
        return None


def get_commit_suffix(path: str):
    branch_commit = get_branch_commit(path)
    if branch_commit:
        return ":" + branch_commit[0] + ":" + branch_commit[1]
    else:
        return ""


def project_repo():
    return os.path.basename(os.path.abspath(os.curdir)) + get_commit_suffix(".")


def hello():
    print(clr(f"Liftoff {version():s} @ {project_repo():s}", attrs=["bold"]))
