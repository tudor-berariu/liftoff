def ord_dict_to_string(dct: dict):
    sorted_keys = sorted(list(dct.keys()))
    sorted_pairs = []
    for key in sorted_keys:
        value = str(dct[key])
        for char in " -.,=:;/()[]'+":
            value = value.replace(char, "_")
        while "___" in value:
            value = value.replace("__", "_")
        sorted_pairs.append(f"{str(key):s}_{value:s}")
    return "__".join(sorted_pairs)
