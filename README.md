# liftoff #

  - launch multiple local experiments;
  - read config files;

## Configuration files ##

#### Assumptions ####
  - you configure parameters for your experiments using `yaml` files
  - you keep those configuration files in a folder called `./configs/`
  - you may want to use two files:
    - one with a default configuration
	- another one that specifiies what should be changed
  - you might want to run batches of experiments


#### Reading configurations ####

`read_config` reads an YAML config file and transforms it to a `Namespace`.

 * 1st use (when `--config_file` and `--default_config_file` are provided)

    -  It reads two config files and combines their info into a
    Namespace. One is supposed to be the default configuration with
    the common settings for most experiments, while the other
    specifies what changes. The YAML structure is transformed into a
    Namespace excepting keys ending with '_'. The reason for this
    behaviour is the following: sometimes you want to overwrite a full
    dictionary, not just specific values (e.g. args for optimizer).

 * 2nd use (when `--experiment` is provided)

    - There must be a folder with the experiment name in ./configs/
    and there several YAMLs:
      - `./configs/<experiment_name>/default.yaml`
      - `./configs/<experiment_name>/<experiment_name>_[...].yaml`

    - Each of those files is combined with default exactly as above. A
    list of `Namespace`s is returned.

#### Launching experiments ####

    liftoff module.function --procs-no n --experiment <experiment_name>


#### Example ####

See [this project](https://github.com/tudor-berariu/lifelong-learning)
