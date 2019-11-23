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


## Quick install

Pip install directly from the master:

```sh
pip install git+git://github.com/tudor-berariu/liftoff.git#egg=liftoff --process-dependency-links
```


## Short tutorial on using `liftoff` ##

After installing `liftoff` go to `./examples/`.

```sh
cd examples
```

Remove all previous results:

```
rm -r results/*
```

### The test script ###

The test script is called `smart_example.py`. It takes three numbers
and adds them together. The arguments are expected in a `Namespace`
with this structure:

```python
Namespace(x=2, yz=Namespace(y=3,z=4))
```

The script sleeps for some seconds and the prints the sum of those
numbers.

### Monitoring liftoff processes ###

Split your terminal and run:

```sh
watch -c -n 1 liftoff-status -a
```

Observe running liftoff experiments there as we go through this tutorial.

### Run it once ###

`liftoff` is useful even when you run a single script once. It reads
the config file for you and then calls the function `run` from that
module.

Run the following command:

```sh
liftoff smart_example.py
```

The above command is equivalent to:

```sh
liftoff smart_example.py --default-config-file default --config-file default
```

You should see the experiment listed by `liftoff-status`.

### Run a small variation ###

In `configs/default.yaml` there are several variables
declared. Imagine you just want to change a few of them from your
default configuration of the experiment.

File `config/diff.yaml` sets different values for `x` and `z`. Run

```sh
liftoff smart_example.py -c diff
```

### Run the same configuration several times ###

Running:

```liftoff smart_example.py --runs-no 4 --procs-no 1
```

will just run the above script with the default configuration several
times. Each run will be run in a separate process. But running all
processes in a sequence is not always what you want. `liftoff` can
manage parallel executions for you.

```sh
liftoff smart_example.py --runs-no 40 --procs-no 20
```

If you have multiple GPUs, you can even limit the maximum number of
concurrent experiments on a single GPU. Running:

```sh
liftoff smart_example.py --runs-no 40 --procs-no 20 --gpus 0,1,2,3 --per-gpu 2
```

will allow no more than 2 experiments on each GPU, so even if
`procs-no` is 20, the maximum number of experiments running in
parallel will be 8.

### Run batches of experiments ###

Sometimes you want to test several combinations of values for multiple
hyperparameters. `liftoff` does that for you.

See that in folder `./configs/test_experiment/` there are two files:
the default configuration `default.yaml` and a file that specifies
multiple values for some variables: `config.yaml`.

First run

```sh
liftoff-prepare test_experiment
```

to generate all config
files. Run `ls configs/test_experiment/` to see what has been generated.

Now run

```sh
liftoff smart_example.py -e test_experiment --comment "My first experiment"
```
to run all those variations.

### Killing processes ###

You can kill the most recent launched liftoff experiment:
`liftoff-abort`, or the most recent one with a given name
`liftoff-abort -e test_experiment`, or a specific one by giving its
timestamp: `liftoff-abort -t 1524936339`.

So, let's see how that works.

  - launch an experiment: `nohup liftoff smart_example.py -e test_experiment --runs-no 20 &`
  - see it running: `liftoff-status -e test_experiment`
  - kill it: `liftoff-abort`


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


```python
def run(opts):
    ...


def main():
    from liftoff import parse_opts
    opts = parse_opts()
    run(opts)


if __name__ == "__main__":
    main()
```




#### Example ####

See example under `./example` where script `smart_example.py` adds `x`, `yz.y` and `yz.z`.

Run `rm -r results/*` to delete results from previous runs.

##### Run a single experiment #####

In order to run an experiment reading the configuration from
`./configs/default.yaml` simply run `liftoff smart_example` or
`liftoff smart_example.py`.


```sh
liftoff smart_example.py
```

You shoud see the program's output and also results saved in
`./results/<timestamp>_default/`.


##### Run the default configuration several times #####

You can run an experiment several times using `--runs-no`:


```sh
liftoff smart_example.py --runs-no 12 --procs-no 4  --no-detach
```


A new folder under `./results/` should appear with a subfolder for
each run.  The previous command made all processes output to the
screen. Chaos. In order to redirect the output of each process to a
separate file detach processes using system commands executed with `nohup`.


```sh
liftoff smart_example --runs-no 12 --procs-no 4
```



##### Running batches of experiments #####

See `./configs/test_experiment/config.yaml` for an example of
configuring a batch of experiments. You should firrst run
`liftoff-prepare` to generate all the necessary config files, and then
launch the experiment with `liftoff -e`.


```sh
liftoff-prepare test_experiment -c
liftoff-prepare test_experiment
liftoff smart_example.py -e test_experiment --procs-no 4
```


##### Filter out some unwanted configurations #####


See the `filter_out` section in `./configs/filter_out/config.yaml`. Some
combinations of values will be discarded.


```sh
liftoff-prepare filter_out -c
liftoff-prepare filter_out
liftoff smart_example.py -e filter_out
```


Also, See [this project](https://github.com/tudor-berariu/lifelong-learning)



## Some useful commands to use when inspecting results ##

If you have several runs that ended in error but you suspect that some
error occurs more than once, you might want to count unique crash
reasons. Replace `<timestamp>` in the command below:


```sh
grep "" results/<timestamp>*/*/*/err | cut -d":" -f1 | sort | uniq | xargs -r -n 1 -- md5sum | cut -f 1 -d " " | sort | uniq -c
```

The above command gives you a list of md5 sums (of `err` files) and a
count for each. If you want to see a particular error message replace
`<md5sum>` in the command below:



```sh
grep "" results/<timestamp>*/*/*/err | cut -d":" -f1 | sort | uniq | xargs -r -n 1 -- md5sum | grep <md5sum> | tail -n 1| cut -f 3 -d" " | xargs -r -n 1 -I_file -- sh -c 'echo "_file" ; cat _file'
```
