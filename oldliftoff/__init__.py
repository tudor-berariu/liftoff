from .liftoff import parse_args
from .config import read_config, config_to_string
from .common.lookup import create_new_experiment_folder


def prepare_experiment():
    import os
    import os.path

    args = parse_args()  # type: Namespace
    cfg = read_config(strict=False)

    if not hasattr(args, "out_dir") or args.out_dir is None:
        _full_name, experiment_path = create_new_experiment_folder(
            cfg.experiment, args.timestamp_fmt, args.results_dir
        )
        cfg.out_dir = experiment_path
    elif not os.path.isdir(args.out_dir):
        raise Exception(f"Directory {args.out_dir} does not exist.")

    if not hasattr(args, "run_id"):
        cfg.run_id = 0

    print(config_to_string(cfg))
    return cfg
