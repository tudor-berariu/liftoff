import os
import os.path
import yaml


def update_configs(original, diff):
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


def save_local_options(update_cfg: dict):
    local_cfg = get_liftoff_config(only_local=True)
    if local_cfg is None:
        local_cfg = update_cfg
    else:
        update_configs(local_cfg, update_cfg)
    with open(".liftoff_cfg.yaml", "w") as handler:
        yaml.safe_dump(local_cfg, handler, default_flow_style=False)
