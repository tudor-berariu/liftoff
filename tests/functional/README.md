Functional tests for checking the results of running the CLI of several liftoff components.

WARNING: these tests need to be ran sequentialy as they will interract between themselves.

They also might be affected by how many resources are available.

Run the tests from the project root folder with:
```
python -m pytest tests 
```

## Example command for manual run:

### Prepare
```
liftoff-prepare /mnt/d/Work/repos/liftoff/tests/functional/shared_test_resources/example_configs_1 --do
```

### Liftoff
```
liftoff example_experiment.py ./results/2024Jan22-233400_example_configs_1 --procs-no 2
```

