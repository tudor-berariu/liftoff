from typing import Dict, List
from copy import copy


def unambiguous_lstrip(keys: List[str], sep: str = ".") -> Dict[str, str]:
    if len(set(keys)) != len(keys):
        raise ValueError("Given list should not have duplicates")

    key_info = {key: (key.split(sep), 1) for key in keys}
    names = {k: sep.join(parts[-idx:]) for k, (parts, idx) in key_info.items()}

    while len(set(names.values())) != len(keys):
        crt_name_set, doubles = set({}), set({})
        for key, name in names.items():
            if name in crt_name_set:
                doubles.add(name)
            crt_name_set.add(name)
        old_names = copy(names)
        for key, name in old_names.items():
            if name in doubles:
                parts, idx = key_info[key]
                idx = min(len(parts), idx + 1)
                new_name = sep.join(parts[-idx:])
                key_info[key] = (parts, idx)
                names[key] = new_name
    return names


def ord_dict_to_string(dct: dict,
                       lstrip: bool = True,
                       ignore: List[str] = None) -> str:
    if ignore:
        dct = {key: value for (key, value) in dct.items() if key not in ignore}
    if lstrip:
        short_keys = unambiguous_lstrip(list(dct.keys()))
        sorted_keys = sorted(list(dct.keys()), key=lambda k: short_keys[k])
    else:
        sorted_keys = sorted(list(dct.keys()))

    sorted_pairs = []
    for key in sorted_keys:
        value = str(dct[key])
        for char in " ,=:;/()[]'+":
            value = value.replace(char, "_")
        while "___" in value:
            value = value.replace("__", "_")
        if lstrip:
            sorted_pairs.append(f"{short_keys[key]:s}_{value:s}")
        else:
            sorted_pairs.append(f"{str(key):s}_{value:s}")
    return "__".join(sorted_pairs)
