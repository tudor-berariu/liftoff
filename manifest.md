# Liftoff v0.3 Manifest #

This is what we aim to improve over liftoff v0.2x

  - one should be able to launch several instances of `liftoff` on different
    machines while operating over the same experiment in the same storage

    - the soluton is to use a `.__lock` file such that no two instances of
      liftoff work in the same folder

  - once an experiment has started, all its details are in that folder

    - in order to achieve this we'll move the creation of folders for individual
      runs in the functionality of `liftoff-prepare`

  - one should add new sub-experiments to an existing one or increase the
    number of runs dynamically


The commands we intend to provide are:

  - `liftoff` which launches individual experiments or runs the sub-experiments
    in a folder

    - ways to invoke it:

        ```
        liftoff script.py -c dqn
        liftoff script.py --config-file dqn
        liftoff script.py --config-dir ./configs -c dqn
        liftoff script.py -c ./configs/dqn.yaml
        ```

        ```
        liftoff script.py -e dqn
        liftoff script.py --experiment dqn
        liftoff script.py -e dqn_13March2019
        liftoff script.py -e ./results/dqn_13March2019
        liftoff script.py --experiments-dir ./results -e dqn -t 13March2019
        
        liftoff script.py -e dqn --runs-no 5 --gpus 0 1 2 --per-gpu 3 --procs-no 5
        ```

  - `liftoff-prepare` configures all the needed sub-experiments, and creates
    the folder structure


The `results-dir` folder structure:

  ```
  results
    {experiment}_{timestamp}/
      .__{session_id}
      {sub-experiment hash}/
        .__hash
        run_{run_id}/
          .__leaf
          .__start
          .__end
          .__crash
          .__journal
          .__lock
          out
          err
  ```


## Development plan

 1. Implement `liftoff-prepare`
 1. Implement `liftoff`
 1. Implement `liftoff-status`
 1. Implement `liftoff-elite`
 1. Implement `liftoff-commit`