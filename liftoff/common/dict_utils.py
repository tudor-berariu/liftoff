""" Here we provide some useful functions to work with dictionaries.
"""

from argparse import Namespace
import hashlib
import operator


def uniqstr(obj):
    """ This function attempts to get unique string representations of objects
        containing dictionaries that are inherently orderless.

        It's purpose is almost impossible, so this represents just a lame
        attempt to get that representation. Nonetheless it should be enough for
        our case.
    """

    if isinstance(obj, dict):
        sorted_dict = sorted(obj.items(), key=operator.itemgetter(0))
        elems = [f"{uniqstr(k)}_{uniqstr(v)}" for (k, v) in sorted_dict]
        return ",".join(elems)
    if isinstance(obj, list):
        return ",".join([uniqstr(elem) for elem in obj])
    return repr(obj)


def hashstr(string):
    """ I use some hash function, the first I laid my eyes on, to get a shorter
        string from the given one.
    """
    return hashlib.sha224(string.encode()).hexdigest()


def deep_update_dict(dct1, dct2, delete_entries=False):
    """ Updates the value from a given recursive dictionary with those from a
        second one.
    """

    for key, value in dct2.items():
        if delete_entries and value == "delete" and key in dct1:
            del dct1["key"]
        elif key.startswith("_"):
            dct1[key] = value
        elif isinstance(value, dict):
            if key in dct1 and isinstance(dct1[key], dict):
                deep_update_dict(dct1[key], value)
            else:
                dct1[key] = value
        else:
            dct1[key] = value

    return dct1


def clean_dict(dct):
    """ [deeply] Removes entries marked with delete from the dictionary.
    """
    if isinstance(dct, dict):
        to_del = []
        for key, value in dct.items():
            if value == "delete":
                to_del.append(key)
            elif isinstance(value, dict):
                clean_dict(value)
        for key in to_del:
            del dct[key]


def dict_to_namespace(dct: dict) -> Namespace:
    """Deep (recursive) transform from Namespace to dict"""
    namespace = Namespace()
    for key, value in dct.items():
        name = key.rstrip("_")
        if isinstance(value, dict) and not key.endswith("_"):
            setattr(namespace, name, dict_to_namespace(value))
        else:
            setattr(namespace, name, value)
    return namespace

