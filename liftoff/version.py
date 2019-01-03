import os
import git
from termcolor import colored as clr

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
        return ":"


def version() -> str:
    import liftoff

    commit = get_commit_suffix(liftoff.__file__)
    return "0.22" + commit  # TODO: change this when a ne version is released


def project_repo():
    return os.path.basename(
        os.path.abspath(os.curdir)
    ) + get_commit_suffix(".")


def welcome_msg(color: bool = True) -> str:
    if color:
        return (
            clr(
                " Liftoff " + version() + " ",
                "white",
                "on_magenta",
                attrs=["bold"],
            )
            + " @ "
            + clr(
                " " + project_repo() + " ", "white", "on_cyan", attrs=["bold"]
            )
        )
    return f"Liftoff {version():s} @ {project_repo():s}"


def welcome() -> None:
    print("\n" + welcome_msg(color=False) + "\n")


if __name__ == "__main__":
    welcome()
