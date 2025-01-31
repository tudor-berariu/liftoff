from argparse import Namespace
from pathlib import Path
from typing import Any, Self

import yaml


# TODO: separate a FlatDict class.
class LO(Namespace):
    """[L]iftoff[O]ptions is a Namespace with support for:
    - loading and saving `yaml`
    - convert to and from `dict` and flat `dict`
    - very pretty printing
    - a special convention where fields ending in `_`, eg.: `message_`, are
    preserved as is, usually dicts.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @staticmethod
    def from_namespace(n: Namespace) -> "LO":
        lopt = LO()
        for key, value in n.__dict__.items():
            if isinstance(value, Namespace):
                setattr(lopt, key, LO.from_namespace(value))
            else:
                setattr(lopt, key, value)
        return lopt

    @staticmethod
    def from_dict(d: dict) -> "LO":
        """Recursive conversion of a dict in a LiftOpt.
        Both `a` and `a_` keys are added tot the Namespace:
            - `a` to to facilitate argument passing like `f(**opt.field)`.
            - `a_` is required to allow casting to dict and flat dict.
        """
        lopt = LO()
        for key, value in d.items():
            name = key.rstrip("_")
            if isinstance(value, dict) and not key.endswith("_"):
                setattr(lopt, name, LO.from_dict(value))
            else:
                setattr(lopt, name, value)
                setattr(lopt, key, value)
        return lopt

    def to_dict(self, d=None) -> dict:
        """Recursive conversion from LiftoffOptions/Namespace to dict.
        Key `a` is evicted if `a_` exists.
        """
        d = self if d is None else d
        dct: dict = {}
        for key, value in d.__dict__.items():
            skey = key.rstrip("_")
            if skey in dct:
                dct.pop(skey)
            if isinstance(value, Namespace):
                dct[key] = self.to_dict(value)
            else:
                dct[key] = value
        return dct

    def from_flat_dict(flat_dict: dict) -> "LO":
        """Expand {a: va, b.c: vbc, b.d: vbd} to {a: va, b: {c: vbc, d: vbd}}.

        Opposite of `flatten_dict`.

        If not clear from above we want:
            {'lr':             0.0011,
            'gamma':           0.95,
            'dnd.size':        2000,
            'dnd.lr':          0.77,
            'dnd.sched.end':   0.0,
            'dnd.sched.steps': 1000}
        to:
            {'lr': 0.0011,
            'gamma': 0.95,
            'dnd': {
                'size': 2000,
                'lr': 0.77,
                'sched': {
                    'end': 0.0,
                    'steps': 1000
            }}}
        """
        exp_dict = {}
        for key, value in flat_dict.items():
            if "." in key:
                keys = key.split(".")
                key_ = keys.pop(0)
                if key_ not in exp_dict:
                    exp_dict[key_] = LO._expand_from_keys(keys, value)
                else:
                    exp_dict[key_] = LO._recursive_update(
                        exp_dict[key_], LO._expand_from_keys(keys, value)
                    )
            else:
                exp_dict[key] = value
        return LO.from_dict(exp_dict)

    def to_flat_dict(self) -> dict:
        d = self.to_dict()
        return LO._flatten_dict(d)

    def from_yaml(path: str | Path) -> "LO":
        """Read a config file and return a namespace."""
        with open(path) as handler:
            config_data = yaml.load(handler, Loader=yaml.SafeLoader)
        return LO.from_dict(config_data)

    def to_yaml(self, path: str | Path) -> None:
        d = LO.sanitize_dict(self.to_dict())
        # TODO: figure out how to sanitize it.
        with open(Path(path), "w") as outfile:
            yaml.safe_dump(d, outfile, default_flow_style=False)

    @staticmethod
    def sanitize_dict(d: dict) -> dict:
        d_ = {}
        for k, v in d.items():
            if isinstance(v, dict):
                d_[k] = LO.sanitize_dict(v)
            # ugly...
            elif not isinstance(v, (bool, int, float, str, list, tuple, dict)):
                d_[k] = str(v)
            else:
                d_[k] = v
        return d_

    @staticmethod
    def _flatten_dict(d: dict, prev_key: str = None) -> dict:
        """Recursive flatten a dict. Eg.: `{a: {ab: 0}}` -> `{a.ab: 0}`."""
        flat_dct: dict = {}
        for key, value in d.items():
            new_key = f"{prev_key}.{key}" if prev_key is not None else key
            if isinstance(value, dict):
                flat_dct.update(LO._flatten_dict(value, prev_key=new_key))
            else:
                flat_dct[new_key] = value
        return flat_dct

    @staticmethod
    def _expand_from_keys(keys: list, value: object) -> dict:
        """Expand [a, b c] to {a: {b: {c: value}}}"""
        dct = d = {}
        while keys:
            key = keys.pop(0)
            d[key] = {} if keys else value
            d = d[key]
        return dct

    @staticmethod
    def _recursive_update(d: dict, u: dict) -> dict:
        "Recursively update `d` with stuff in `u`."
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = LO._recursive_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    @staticmethod
    def _to_str(lopt: Self, indent: int = 0):
        s = ""
        for key, value in lopt.__dict__.items():
            if key.endswith("_"):
                continue
            s += f"{key:>{len(key) + indent}s}: "
            if isinstance(value, LO):
                s += f"\n{LO._to_str(value, indent + 2)}"
            else:
                s += f"{value}\n"
        return s

    def __str__(self):
        return LO._to_str(self)

    # handy platform information
    @staticmethod
    def _get_cpu_name():
        import os
        import platform
        import re
        import subprocess

        if platform.system() == "Windows":
            return platform.processor()
        elif platform.system() == "Darwin":
            os.environ["PATH"] = os.environ["PATH"] + os.pathsep + "/usr/sbin"
            command = "sysctl -n machdep.cpu.brand_string"
            return subprocess.check_output(command).strip()
        elif platform.system() == "Linux":
            command = "cat /proc/cpuinfo"
            all_info = subprocess.check_output(command, shell=True).decode().strip()
            for line in all_info.split("\n"):
                if "model name" in line:
                    return re.sub(".*model name.*:", "", line, 1)
        return ""

    @staticmethod
    def _get_cpu_info():
        keys = (
            "brand_raw",
            "count",
            "hz_advertised_friendly",
            "hz_actual_friendly",
            "flags",
        )
        try:
            import cpuinfo

            cpu = {k: v for k, v in cpuinfo.get_cpu_info().items() if k in keys}
        except ModuleNotFoundError:
            cpu = "install `cpuinfo` to use this feature"

        return cpu

    @staticmethod
    def _get_gpu_name():
        try:
            import gpustat
            import pynvml

            gpu = gpustat.new_query()[0].entry["name"]
        except ModuleNotFoundError:
            gpu = "install `gpustat` to use this feature"
        except pynvml.NVMLError:
            gpu = "`gpustat` can't find gpu"

        return gpu

    def platform(self) -> "LO":
        import os
        import socket

        lo = LO(
            host=socket.gethostname(),
            cpu=LO._get_cpu_name(),
            gpu=LO._get_gpu_name(),
            cpuinfo_=LO._get_cpu_info(),
        )
        if ont := os.getenv("OMP_NUM_THREADS"):
            setattr(lo, "omp_num_threads", ont)

        setattr(self, "platform", lo)
        return self
