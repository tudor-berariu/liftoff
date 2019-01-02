import os
import os.path
from typing import List, Optional
import yaml


def update_configs(original, diff):
    """ This function takes updates the first dictionary using values from the
        second. It an entry in the second dictionary has a key starting with
        '_' then it replaces the full value (removing the '_') instead of going
        recurisively in depth.
    """

    for key, value in diff.items():
        if key.startswith("_"):
            original[key[1:]] = value
        elif not isinstance(value, dict) or key not in original:
            original[key] = value
        else:
            if not isinstance(original[key], dict):
                raise RuntimeError("Cannot overwrite value with dictionary.")
            update_configs(original[key], value)


def get_liftoff_config(only_local: bool = False) -> dict:
    """ This function returns a dictionary with all the settings for liftoff.
        It first loads the global config from ~/.liftoff_cfg.yaml (if exists).
        If there is a local (project) configuration it is used to update the
        global configuration.
    """

    local_cfg, global_cfg = None, None

    if os.path.isfile(".liftoff_cfg.yaml"):
        with open(".liftoff_cfg.yaml") as handler:
            local_cfg = yaml.load(handler, Loader=yaml.SafeLoader)
    if not only_local and os.path.isfile("~/.liftoff_cfg.yaml"):
        with open("~/.liftoff_cfg.yaml") as handler:
            global_cfg = yaml.load(handler, Loader=yaml.SafeLoader)

    if global_cfg is None:
        return local_cfg

    if local_cfg is None:
        return global_cfg

    update_configs(global_cfg, local_cfg)
    return global_cfg


def get_liftoff_option(keys: List[str]) -> Optional[object]:
    """ This function reads some option from the config file. It should be used
        only when one is not interested in more than one setting. In that case
        call 'get_liftoff_config' and get all the values you need form that
        dictionary.
    """

    liftoff_cfg = get_liftoff_config()
    for key in keys:
        if not isinstance(liftoff_cfg, dict) or key not in liftoff_cfg:
            return None
        liftoff_cfg = liftoff_cfg[key]
    return liftoff_cfg


def save_local_options(update_cfg: dict):
    local_cfg = get_liftoff_config(only_local=True)
    if local_cfg is None:
        local_cfg = update_cfg
    else:
        update_configs(local_cfg, update_cfg)
    with open(".liftoff_cfg.yaml", "w") as handler:
        yaml.safe_dump(local_cfg, handler, default_flow_style=False)
