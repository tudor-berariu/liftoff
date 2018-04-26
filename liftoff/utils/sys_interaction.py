import subprocess


def systime_to(timestamp_file_path: str) -> None:
    cmd = f"date +%s 1> {timestamp_file_path:s}"
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
    (_, err) = proc.communicate()
    return err.decode("utf-8").strip()
