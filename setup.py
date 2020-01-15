""" This is the install script. Be careful to update the version from time to
    time and to add any additional entry points as you develop them. Also,
    please keep the requirements list up to date.
"""

from setuptools import setup, find_packages


VERSION = '0.3.1' # single source of truth
print('-- Installing liftoff ' + VERSION)
with open("./liftoff/version.py", 'w') as f:
    f.write("__version__ = '{}'\n".format(VERSION))


setup(
    name="liftoff",
    version=VERSION,
    description="Experiment launcher; AGI assistant",
    entry_points={
        "console_scripts": [
            "liftoff-prepare=liftoff.cmd:prepare",
            "liftoff=liftoff.cmd:liftoff",
            "liftoff-abort=liftoff.cmd:abort",
            "liftoff-procs=liftoff.cmd:procs",
            "liftoff-clean=liftoff.cmd:clean",
            "liftoff-status=liftoff.cmd:status",
            "liftoff-lock=liftoff.cmd:lock",
            "liftoff-unlock=liftoff.cmd:unlock",
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
