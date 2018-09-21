from typing import Dict, List, Tuple
from copy import deepcopy
from argparse import Namespace
import numpy as np

from liftoff.config import namespace_to_dict


# -- Numbers  digit ** (10 ** order)

def to_number(value: Tuple[int, int]) -> float:
    digit, order = value
    return digit * (10 ** order)


def mutate_number(value: Tuple[int, int],
                  avoid_zero: bool = True,
                  positive: bool = True,
                  min_order: int = 0,
                  max_order: int = 5,
                  precision: int = 1) -> Tuple[int, int]:
    digit, order = value
    limit = 10 ** precision - 1
    changed = False
    while not changed:
        sample = np.random.sample()
        if sample < .25 and order < max_order:
            order, changed = order + 1, True
        elif sample < .5 and order > min_order:
            order, changed = order - 1, True
        elif sample < .75 and digit < limit:
            digit += 2 if (digit == -1 and avoid_zero) else 1
            changed = True
        elif (not positive and digit > -limit):
            digit -= 2 if (digit == 1 and avoid_zero) else 1
            changed = True
        elif (not avoid_zero and digit > 0) or digit > 1:
            digit -= 1
            changed = True
    return [digit, order]


def random_number(avoid_zero: bool = None,
                  positive: bool = None,
                  min_order: int = None,
                  max_order: int = None,
                  precision: int = None) -> bool:
    max_limit = 10 ** precision
    min_limit = (1 if avoid_zero else 0) if positive else (1 - max_limit)
    digit = np.random.randint(min_limit, max_limit)
    order = np.random.randint(min_order, max_order + 1)
    return [digit, order]


def check_number(value: object,
                 avoid_zero: bool=None,
                 positive: bool=None,
                 min_order: int=None,
                 max_order: int=None,
                 precision: int=None) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    digit, order = list(map(int, value))
    if avoid_zero and (digit == 0):
        return False
    if positive and digit < 0:
        return False
    if precision is not None:
        limit = 10 ** precision - 1
        if digit > limit or digit < -limit:
            return False
    if min_order is not None and order < min_order:
        return False
    if max_order is not None and order > max_order:
        return False
    return True


# -- Powers of two

def mutate_power_of_two(value: float, min_power=0, max_power=10) -> float:
    crt_power = int(np.log(value) / np.log(2))
    while True:
        sample = np.random.sample()
        if sample < .5 and crt_power > min_power:
            crt_power -= 1
            break
        elif crt_power < max_power:
            crt_power += 1
            break
    return 2 ** crt_power


def random_power_of_two(min_power: int = 0, max_power: int = 10) -> float:
    power = np.random.randint(min_power, max_power + 1)
    return 2 ** power


def check_power_of_two(value: object, min_power=None, max_power=None) -> None:
    crt_power = int(np.log(value) / np.log(2))
    if min_power is not None and crt_power < min_power:
        return False
    if max_power is not None and crt_power > max_power:
        return False
    return True


# -- Categorical

def mutate_set_member(value: object, domain: List[object]) -> object:
    new_value = domain[np.random.randint(len(domain))]
    while value == new_value and len(domain) > 1:
        new_value = domain[np.random.randint(len(domain))]
    return new_value


def check_set_member(value: object, domain: List[object]) -> bool:
    return value in domain


def random_from_set(domain: List[object]) -> object:
    return domain[np.random.randint(len(domain))]


# -- Impose constraints (no cycles, please)

def correct_args(args: Namespace,
                 constraints: Dict[str, Dict[object, List[Tuple[str, object]]]]
                 ) -> None:
    to_check = [var_name for var_name in constraints.keys()]
    while to_check:
        var_name = to_check.pop(0)
        if var_name in constraints:
            cons = constraints[var_name]
            value = getattr(args, var_name)
            if value in cons:
                for var, val in cons[value]:
                    setattr(args, var, val)
                    to_check.append(var)


class Mutator:

    MUTATE_FS = {
        "number": mutate_number,
        "ptwo": mutate_power_of_two,
        "set": mutate_set_member
    }

    CHECK_FS = {
        "number": check_number,
        "ptwo": check_power_of_two,
        "set": check_set_member
    }

    def __init__(self, variables: Dict[str, Tuple[str, dict]],
                 constraints: Dict[str, Dict[object, List[Tuple[str, object]]]]):
        self.variables = variables
        self.constraints = constraints

        assert isinstance(variables, dict)
        for var_name, cons in constraints.items():
            assert var_name in variables and isinstance(cons, dict)
            for _var_value, assoc in cons.items():
                assert isinstance(assoc, list)
                for other_var_name, _other_var_value in assoc:
                    assert other_var_name in variables

    def mutate(self, args: Namespace) -> Namespace:
        args = deepcopy(args)
        var_name = np.random.choice(list(self.variables.keys()))
        var_type, kwargs = self.variables[var_name]
        new_value = Mutator.MUTATE_FS[var_type](args.__dict__[var_name], **kwargs)
        args.__dict__[var_name] = new_value
        correct_args(args, self.constraints)
        return args

    def crossover(self, args1: Namespace, args2: Namespace) -> Namespace:
        args = deepcopy(args1)
        for var_name in self.variables.keys():
            if np.random.sample() < .5:
                args.__dict__[var_name] = args2.__dict__[var_name]
        correct_args(args, self.constraints)
        return args

    def check_args(self, args: Namespace) -> bool:
        for (var_name, (var_type, kwargs)) in self.variables.items():
            if var_name not in args:
                return False
            if not Mutator.CHECK_FS[var_type](getattr(args, var_name), **kwargs):
                return False
        return True

    def sample(self) -> Namespace:
        args = Namespace()
        for (var_name, (var_type, kwargs)) in self.variables.items():
            if var_type == "number":
                setattr(args, var_name, random_number(**kwargs))
            elif var_type == "ptwo":
                setattr(args, var_name, random_power_of_two(**kwargs))
            elif var_type == "set":
                setattr(args, var_name, random_from_set(**kwargs))
            else:
                raise ValueError
        correct_args(args, self.constraints)
        return args

    def to_phenotype(self, genotype: Namespace) -> Namespace:
        phenotype = Namespace()
        for var_name, (var_type, _) in self.variables.items():
            elements = var_name.split('.')
            sub_cfg = phenotype
            for element_name in elements[:-1]:
                if not hasattr(sub_cfg, element_name):
                    setattr(sub_cfg, element_name, Namespace())
                sub_cfg = getattr(sub_cfg, element_name)
            if var_type == "number":
                value = to_number(getattr(genotype, var_name))
            else:
                value = deepcopy(getattr(genotype, var_name))
            setattr(sub_cfg, elements[-1], value)
        return phenotype


def get_mutator(cfg: Namespace) -> Mutator:
    cfg = namespace_to_dict(cfg)
    tmp_vars = [("", cfg)]
    final_vars = {}
    while tmp_vars:
        print(tmp_vars)
        prev_path, sub_cfg = tmp_vars.pop(0)
        if "gtype" in sub_cfg.keys():
            kwargs = {k: v for (k, v) in sub_cfg.items() if k != "gtype"}
            final_vars[prev_path] = (sub_cfg["gtype"], kwargs)
        else:
            for key, value in sub_cfg.items():
                if key not in ["meta", "constraints"]:
                    assert "." not in key
                    new_path = ((prev_path + ".") if prev_path else "") + key
                    tmp_vars.append((new_path, value))
    if hasattr(cfg, "constraints"):
        constraints = namespace_to_dict(cfg.constraints)
        for var_name, var_constraints in constraints.items():
            for value, tuples in var_constraints.items():
                for var_name, _value in tuples:
                    assert var_name in final_vars
    else:
        constraints = {}
    return Mutator(final_vars, constraints)


def __test():
    args = Namespace(a=2, b=[3, -2], c="foo", d=[-2, 2], e="constant")
    prev_args = args
    prev_args.c = "bar"
    prev_args.a = 32

    mutator = Mutator({"a": ("ptwo", {"min_power": 0,  # An integer value
                                      "max_power": 5}),
                       "b": ("number", {"min_order": -3,
                                        "max_order": 3,
                                        "positive": True,
                                        "avoid_zero": False}),
                       "c": ("set", {"domain": ["foo", "bar"]}),
                       "d": ("number", {"min_order": -3,
                                        "max_order": 3,
                                        "positive": False,
                                        "avoid_zero": False})},

                      constraints={"a": {16: [("c", "bar")]}})

    for _ in range(25):
        new_args = mutator.crossover(args, prev_args)
        new_args = mutator.mutate(new_args)
        mutator.check_args(new_args)
        prev_args = args
        args = new_args
        print(new_args)


if __name__ == "__main__":
    __test()
