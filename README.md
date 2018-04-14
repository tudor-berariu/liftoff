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


### Scripts to be run ###

Your typical script should have two functions: one that reads
experiment configuration from disk (`main`) and one that takes a
Namespace (`run`).


    def run(args: Args) -> None:
        ...
    
    
    def main():
    
        # Reading args
		from liftoff.config import read_config
        args = read_config()  # type: Args
    
        if not hasattr(args, "out_dir"):
            from time import time
            if not os.path.isdir('./results'):
                os.mkdir('./results')
            out_dir = f'./results/{str(int(time())):s}_{args.experiment:s}'
            os.mkdir(out_dir)
            args.out_dir = out_dir
        else:
            assert os.path.isdir(args.out_dir), "Given directory does not exist"
    
        if not hasattr(args, "run_id"):
            args.run_id = 0
    
        run(args)
    
    
    if __name__ == "__main__":
        main()
    



#### Example ####







See [this project](https://github.com/tudor-berariu/lifelong-learning)
