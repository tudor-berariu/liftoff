# liftoff #

  - launch local experiments using `liftoff`;
    * launch single runs: `liftoff smart_example.py -c diff`
	* launch multiple runs of the same configuration `liftoff smart_example.py --runs-no 10 --procs-no 3`
	* launch batches of experiments: `liftoff -e test_experiment --gpus 0,1 --per-gpu 2 --procs-no 4`
  - prepare batches of experiments using `liftoff-prepare`;
    * generate configs: `liftoff-prepare test_experiment`
  - see the status of all running experiments: `liftoff-status`
  - see all prevoius experiments: `liftoff-status -a`
  - get paths to all dumped files using `collect_results` from `liftoff.liftoff_results`
  - read and parse config files using `read_config` from `liftoff.config` ;
  - kill running experiments using `liftoff-abort` (no worries, it asks you first)


## Short tutorial on using `liftoff` ##

After installing `liftoff` go to `./examples/`.

```cd examples```

Remove all previous results:

```rm -r results/*```

### The test script ###

The test script is called `smart_example.py`. It takes three numbers
and adds them together. The arguments are expected in a `Namespace`
with this structure:

```Namespace(x=2, yz=Namespace(y=3,z=4))```

The script sleeps for some seconds and the prints the sum of those
numbers.

### Monitoring liftoff processes ###

Split your terminal and run:

```watch -c -n 1 liftoff-status -a```

Observe running liftoff experiments there as we go through this tutorial.

### Run it once ###

`liftoff` is useful even when you run a single script once. It reads
the config file for you and then calls the function `run` from that
module.

Run the following command:

```liftoff smart_example.py```

The above command is equivalent to:

```liftoff smart_example.py --default-config-file default --config-file default```

You should see the experiment listed by `liftoff-status`.

### Run a small variation ###

In `configs/default.yaml` there are several variables
declared. Imagine you just want to change a few of them from your
default configuration of the experiment.

File `config/diff.yaml` sets different values for `x` and `z`. Run

```liftoff smart_example.py -c diff```

### Run the same configuration several times ###

Running:

```liftoff smart_example.py --runs-no 4 --procs-no 1```

will just run the above script with the default configuration several
times. Each run will be run in a separate process. But running all
processes in a sequence is not always what you want. `liftoff` can
manage parallel executions for you.

```liftoff smart_example.py --runs-no 40 --procs-no 20```

If you have multiple GPUs, you can even limit the maximum number of
concurrent experiments on a single GPU. Running:

```liftoff smart_example.py --runs-no 40 --procs-no 20 --gpus 0,1,2,3 --per-gpu 2```

will allow no more than 2 experiments on each GPU, so even if
`procs-no` is 20, the maximum number of experiments running in
parallel will be 8.

### Run batches of experiments ###

Sometimes you want to test several combinations of values for multiple
hyperparameters. `liftoff` does that for you.

See that in folder `./configs/test_experiment/` there are two files:
the default configuration `default.yaml` and a file that specifies
multiple values for some variables: `config.yaml`.

First run ```liftoff-prepare test_experiment``` to generate all config
files. Run `ls configs/test_experiment/` to see what has been generated.

Now run ```liftoff -e test_experiment``` to run all those variations.

## Configuration files ##

#### Assumptions ####

  - you configure parameters for your experiments using `yaml` files
  - you keep those configuration files in a folder called `./configs/`
  - you may want to use two files:
    - one with a default configuration
	- another one that specifiies what should be changed
  - you might want to run batches of experiments
    - each experiment will be configured in his own folder


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
	    - usually, these files are generated with `liftoff-prepare` based on a file `./configs/<experiment_name>/config.yaml`


    - Each of those files is combined with default exactly as above. A
    list of `Namespace`s is returned.


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

See example under `./example` where script `smart_example.py` adds `x`, `yz.y` and `yz.z`.

Run `rm -r results/*` to delete results from previous runs.

##### Run a single experiment #####

In order to run an experiment reading the configuration from
`./configs/default.yaml` simply run `liftoff smart_example` or
`liftoff smart_example.py`.


    liftoff smart_example.py
	

You shoud see the program's output and also results saved in
`./results/<timestamp>_default/`.


##### Run the default configuration several times #####

You can run an experiment several times using `--runs-no`:


    liftoff smart_example.py --runs-no 12 --procs-no 4  --no-detach


A new folder under `./results/` should appear with a subfolder for
each run.  The previous command made all processes output to the
screen. Chaos. In order to redirect the output of each process to a
separate file detach processes using system commands executed with `nohup`.


    liftoff smart_example --runs-no 12 --procs-no 4



##### Running batches of experiments #####

See `./configs/test_experiment/config.yaml` for an example of
configuring a batch of experiments. You should firrst run
`liftoff-prepare` to generate all the necessary config files, and then
launch the experiment with `liftoff -e`.


    liftoff-prepare test_experiment -c
	liftoff-prepare test_experiment
	liftoff smart_example.py -e test_experiment --procs-no 4


##### Filter out some unwanted configurations #####


See the `filter_out` section in
	`./configs/filter_out/config.yaml`. Some combinations of values
	will be discarded.


	liftoff-prepare filter_out -c
	liftoff-prepare filter_out
	liftoff smart_example.py -e filter_out


Also, See [this project](https://github.com/tudor-berariu/lifelong-learning)
