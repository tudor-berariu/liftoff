import subprocess
import os.path
from termcolor import colored as clr


def get_commit():
    try:
        dir_path = os.path.dirname(__file__)
        cmd = f"cd {dir_path:s}; git describe --always"
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        err = err.decode("Utf-8").strip()
        if err:
            print(err)
            return ""
        out = out.decode("Utf-8").strip()
        return "+" + out
    except Exception as e:  # TODO: Catch a more specific exception
        pass
    return ""


def version() -> str:
    commit = get_commit()
    return "0.2.1" + commit


def welcome_msg() -> str:
    return f"\nThis is {clr('Liftoff', 'yellow', attrs=['bold']):s}" \
        f" {version():s}.\n"


def welcome() -> None:
    print(welcome_msg())


if __name__ == "__main__":
    welcome()
