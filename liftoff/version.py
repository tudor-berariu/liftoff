import subprocess
import os.path


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
    except Exception as e:
        pass
    return ""


def version() -> str:
    commit = get_commit()
    return "0.2" + commit


if __name__ == "__main__":
    print(version())
