from typing import Dict, List, Optional, Tuple
from copy import deepcopy
from argparse import Namespace
import numpy as np

from liftoff.config import namespace_to_dict, config_to_string


class GenotypeException(Exception):
    pass


# -- Numbers  digit ** (10 ** order)

def to_number(value: Tuple[int, int]) -> float:
    digit, order = value
    return digit * (10 ** order)


def mutate_number(value: Tuple[int, int],
                  avoid_zero: bool = True,
                  positive: bool = True,
                  min_order: int = 0,
                  max_order: int = 5,
                  precision: int = 1,
                  momentum: Optional[int] = None) -> Tuple[Tuple[int, int], int]:

    digit, order = value
    limit = 10 ** precision - 1
    changed = False
    old_momentum = momentum
    while not changed:
        sample = np.random.sample()
        if (old_momentum == 0 or sample < .25) and order < max_order:
            order, changed, momentum = order + 1, True, 0
        elif (old_momentum == 1 or sample < .5) and order > min_order:
            order, changed, momentum = order - 1, True, 1
        elif (old_momentum == 2 or sample < .75) and digit < limit:
            digit += 2 if (digit == -1 and avoid_zero) else 1
            changed, momentum = True, 2
        elif (not positive and digit > -limit):
            digit -= 2 if (digit == 1 and avoid_zero) else 1
            changed, momentum = True, 3
        elif (not avoid_zero and digit > 0) or digit > 1:
            digit -= 1
            changed, momentum = True, 3
        old_momentum = None
    return [digit, order], momentum


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
                 avoid_zero: bool = None,
                 positive: bool = None,
                 min_order: int = None,
                 max_order: int = None,
                 precision: int = None) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        raise GenotypeException("Expected list of size 2, found " + str(value))
    digit, order = list(map(int, value))
    if avoid_zero and (digit == 0):
        raise GenotypeException("Zero value for non-zero variable")
    if positive and digit < 0:
        raise GenotypeException("Negative value for positive variable")
    if precision is not None:
        limit = 10 ** precision - 1
        if digit > limit or digit < -limit:
            raise GenotypeException("Value " + str(digit) + " outside limits")
    if min_order is not None and order < min_order:
        raise GenotypeException("Order " + order + " less than minimum of " + str(min_order))
    if max_order is not None and order > max_order:
        raise GenotypeException("Order " + order + " more than maximum of " + str(max_order))
    return True


# -- Powers of two

def mutate_power_of_two(value: float,
                        min_power: int = 0,
                        max_power: int = 10,
                        momentum: Optional[int] = None) -> Tuple[float, int]:
    crt_power = int(np.log(value) / np.log(2))
    old_momentum = momentum
    while True:
        sample = np.random.sample()
        if (old_momentum == 0 or sample < .5) and crt_power > min_power:
            crt_power -= 1
            momentum = 0
            break
        elif crt_power < max_power:
            crt_power += 1
            momentum = 1
            break
        old_momentum = None
    return 2 ** crt_power, momentum


def random_power_of_two(min_power: int = 0, max_power: int = 10) -> float:
    power = np.random.randint(min_power, max_power + 1)
    return 2 ** power


def check_power_of_two(value: object, min_power=None, max_power=None) -> None:
    crt_power = int(np.log(value) / np.log(2))
    if min_power is not None and crt_power < min_power:
        raise GenotypeException("Power " + str(crt_power) + " less than minimum of " + str(min_power))
    if max_power is not None and crt_power > max_power:
        raise GenotypeException("Power " + str(crt_power) + " more than maximum of " + str(min_power))
    return True


# -- Categorical

def mutate_set_member(value: object,
                      domain: List[object],
                      momentum: Optional[int] = None) -> object:
    new_value = domain[np.random.randint(len(domain))]
    while value == new_value and len(domain) > 1:
        new_value = domain[np.random.randint(len(domain))]
    return new_value, 0  # no momentum for categorical values


def check_set_member(value: object, domain: List[object]) -> bool:
    if value not in domain:
        raise GenotypeException("Value " + str(value) + " not in domain")
    return True


def random_from_set(domain: List[object]) -> object:
    return domain[np.random.randint(len(domain))]


# -- Impose constraints (no cycles, please)

def correct_args(args: Namespace,
                 constraints: Dict[str, Dict[object, List[Tuple[str, object]]]]
                 ) -> None:
    chain_length, max_chain_length = 0, 100
    to_check = [var_name for var_name in constraints.keys()]
    while to_check:
        assert chain_length < max_chain_length, "To many constrains... looping?"
        var_name = to_check.pop(0)
        if var_name in constraints:
            cons = constraints[var_name]
            value = getattr(args, var_name)
            if value in cons:
                for var, val in cons[value]:
                    setattr(args, var, val)
                    to_check.append(var)
        chain_length += 1


class Mutator:

    MUTATE_FS = {
        "number": mutate_number,
        "ptwo": mutate_power_of_two,
        "set": mutate_set_member
    }

    SAMPLE_FS = {
        "number": random_number,
        "ptwo": random_power_of_two,
        "set": random_from_set
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

    def mutate(self,
               parent_genotype: Namespace,
               parent_fitness: Optional[float] = None,
               follow_momentum: bool = False) -> Namespace:
        grandma_fitness, parent_mutation, parent_momentum = None, None, None
        genotype = deepcopy(parent_genotype)

        if hasattr(genotype, "meta"):
            if hasattr(genotype.meta, "parent_fitness"):
                grandma_fitness = genotype.meta.parent_fitness
            if hasattr(genotype.meta, "mutation"):
                parent_mutation = genotype.meta.mutation
            if hasattr(parent_genotype.meta, "momentum"):
                parent_momentum = genotype.meta.momentum

        var_name, momentum = None, None

        if follow_momentum and parent_fitness is not None:
            if parent_fitness < grandma_fitness:
                # Drop momentum if it did no good
                if hasattr(parent_momentum, parent_mutation):
                    delattr(parent_mutation, parent_mutation)
            if parent_mutation.__dict__:
                var_name = np.random.choice(list(parent_momentum.__dict__.keys()))
                momentum = getattr(parent_momentum, var_name)

        if var_name is None:
            var_name = np.random.choice(list(self.variables.keys()))

        var_type, kwargs = self.variables[var_name]
        old_value = genotype.__dict__[var_name]
        if old_value == "delete":
            new_value = Mutator.SAMPLE_FS[var_type](**kwargs)
        else:
            new_value, momentum = Mutator.MUTATE_FS[var_type](old_value,
                                                              momentum=momentum,
                                                              **kwargs)

        setattr(genotype, var_name, new_value)
        if not hasattr(genotype, "meta"):
            genotype.meta = Namespace()
        genotype.meta.parent_fitness = parent_fitness
        genotype.meta.mutation = var_name
        if not hasattr(genotype.meta, "momentum"):
            genotype.meta.momentum = Namespace()
        setattr(genotype.meta.momentum, var_name, momentum)
        genotype.meta.source = "mutation"

        correct_args(genotype, self.constraints)
        print("Mutated\n{}to\n{}".format(config_to_string(parent_genotype),
                                         config_to_string(genotype)))
        return genotype

    def crossover(self, parent1: Namespace, parent2: Namespace) -> Namespace:
        child = deepcopy(parent1)
        for var_name in self.variables.keys():
            if np.random.sample() < .5:
                child.__dict__[var_name] = parent2.__dict__[var_name]
        child.meta = Namespace(source="crossover")
        correct_args(child, self.constraints)
        print("Combined\n{}and\n{}into\n{}".format(config_to_string(parent1),
                                                   config_to_string(parent2),
                                                   config_to_string(child)))
        return child

    def check_genotype(self, args: Namespace) -> bool:
        for (var_name, (var_type, kwargs)) in self.variables.items():
            if var_name not in args:
                raise GenotypeException("Unknown variable " + str(var_name))
            raw_value = getattr(args, var_name)
            if raw_value == "delete":
                continue
            Mutator.CHECK_FS[var_type](raw_value, **kwargs)
        return True

    def sample(self) -> Namespace:
        genotype = Namespace()
        for (var_name, (var_type, kwargs)) in self.variables.items():
            if var_type == "number":
                setattr(genotype, var_name, random_number(**kwargs))
            elif var_type == "ptwo":
                setattr(genotype, var_name, random_power_of_two(**kwargs))
            elif var_type == "set":
                setattr(genotype, var_name, random_from_set(**kwargs))
            else:
                raise ValueError
        genotype.meta = Namespace(source="sample")
        correct_args(genotype, self.constraints)
        return genotype

    def to_phenotype(self, genotype: Namespace) -> Namespace:
        phenotype = Namespace()
        for var_name, (var_type, _) in self.variables.items():
            elements = var_name.split('.')
            sub_cfg = phenotype
            for element_name in elements[:-1]:
                if not hasattr(sub_cfg, element_name):
                    setattr(sub_cfg, element_name, Namespace())
                sub_cfg = getattr(sub_cfg, element_name)
            raw_value = getattr(genotype, var_name)
            if raw_value == "delete":
                value = "delete"
            elif var_type == "number":
                value = to_number(raw_value)
            else:
                value = deepcopy(raw_value)
            setattr(sub_cfg, elements[-1], value)
        return phenotype


def get_mutator(cfg: Namespace) -> Mutator:
    cfg = namespace_to_dict(cfg)
    tmp_vars = [("", cfg)]
    final_vars = {}
    while tmp_vars:
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
    if "constraints" in cfg:
        new_constraints = {}
        constraints = cfg["constraints"]  # namespace_to_dict(cfg.constraints)
        for var_name, var_constraints in constraints.items():
            new_constraints[var_name] = cvar = {}
            for value, tuples in var_constraints.items():
                cvar[value] = []
                for dct in tuples:
                    for (other_name, other_value) in dct.items():
                        cvar[value].append((other_name, other_value))
                        assert other_name in final_vars
        constraints = new_constraints
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
