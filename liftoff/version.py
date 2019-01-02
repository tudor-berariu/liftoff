import os
import git
from termcolor import colored as clr


def get_active_branch_commit(path: str):
    try:
        repo = git.Repo(path=path, search_parent_directories=True)
        return (
            ":" + repo.active_branch.name + ":" + repo.head.object.hexsha[-7:]
        )
    except git.InvalidGitRepositoryError:
        return ""


def version() -> str:
    import liftoff

    commit = get_active_branch_commit(liftoff.__file__)
    return "0.2.2" + commit  # TODO: change this when a ne version is released


def project_repo():
    return os.path.basename(
        os.path.abspath(os.curdir)
    ) + get_active_branch_commit(".")


def welcome_msg(color: bool = True) -> str:
    if color:
        return (
            "\n"
            + clr(" Liftoff " + version() + " ", "white", "on_magenta")
            + " @ "
            + clr(" " + project_repo() + " ", "white", "on_cyan")
            + "\n"
        )
    return f"\n{version():s} @ {project_repo():s}\n"


def welcome() -> None:
    print(welcome_msg())


if __name__ == "__main__":
    welcome()
