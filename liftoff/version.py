import git
from termcolor import colored as clr


def get_active_banch_commit():
    repo = git.Repo(search_parent_directories=True)
    return ":" + repo.active_branch.name + ":" + repo.head.object.hexsha[-7:]


def version() -> str:
    commit = get_active_banch_commit()
    return "0.2.1" + commit  # TODO: change this when a ne version is released


def welcome_msg() -> str:
    return f"\nThis is {clr('Liftoff', 'yellow', attrs=['bold']):s}" \
        f" {version():s}.\n"


def welcome() -> None:
    print(welcome_msg())


if __name__ == "__main__":
    welcome()
