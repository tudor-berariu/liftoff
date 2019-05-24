""" This is the install script. Be careful to update the version from time to
    time and to add any additional entry points as you develop them. Also,
    please keep the requirements list up to date.
"""

from setuptools import setup, find_packages

setup(
    name="liftoff",
    version="0.3",
    description="Experiment launcher; AGI assistant",
    entry_points={
        "console_scripts": [
            "liftoff-prepare=liftoff.cmd:prepare",
            "liftoff=liftoff.cmd:liftoff",
            "liftoff-abort=liftoff.cmd:abort",
            "liftoff-procs=liftoff.cmd:procs",
            "liftoff-clean=liftoff.cmd:clean",
            "liftoff-status=liftoff.cmd:status",
        ]
    },
    packages=find_packages(),
    url="https://github.com/tudor-berariu/liftoff",
    author="Tudor Berariu",
    author_email="tudor.berariu@gmail.com",
    license="MIT",
    install_requires=["gitpython", "pyyaml", "tabulate", "termcolor", "pyperclip"],
    zip_safe=False,
)
