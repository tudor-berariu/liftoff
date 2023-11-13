import pytest
import os
import re
from ..shared_test_resources.utils import run_cli_command, clean_up_directory

CLEANUP_TESTS_OUTPUTS = False

feature_test_location = os.path.dirname(os.path.realpath(__file__))
shared_resources_location = os.path.join(
    os.path.dirname(feature_test_location), "shared_test_resources"
)
test_temp_output_path = os.path.join(feature_test_location, "tmp")


@pytest.fixture
def method_scoped_directory(request):
    # Get the name of the test method
    method_name = request.node.name
    specific_test_output_path = os.path.join(test_temp_output_path, method_name)

    # Clean up any previous test outputs
    clean_up_directory(specific_test_output_path)

    yield specific_test_output_path  # Provide the path to the test

    # Cleanup after test
    if CLEANUP_TESTS_OUTPUTS:
        clean_up_directory(specific_test_output_path)


class TestProcsCLI:
    
            
    def test_multiple_experiments_procs(self, method_scoped_directory):

        ### Run liftoff-prepare command
        config_directory = "example_configs_1"
        config_folder_path = os.path.join(shared_resources_location, config_directory)

        command = [
            "liftoff-prepare",
            config_folder_path,
            "--results-path",
            method_scoped_directory,
            "--do",
        ]
        run_cli_command(command=command, cwd=feature_test_location)
        
        subdirs = [
            d
            for d in os.listdir(method_scoped_directory)
            if os.path.isdir(os.path.join(method_scoped_directory, d))
        ]
        # Check that there is exactly one subdirectory
        assert len(subdirs) == 1, "There should be exactly one subdirectory"

        # ### Now actually run the liftoff command
        
        # script_name = "example_experiment.py"
        # exp_path = os.path.join(method_scoped_directory, subdirs[0])
        
        # command = [
        #     "liftoff",
        #     script_name,
        #     exp_path,
        #     "--procs-no",
        #     "4",
        # ]
        # run_cli_command(
        #     command=command,
        #     cwd=feature_test_location,
        # )
        
        ### Check that there are 4 processes running, and they are shown
        
            
    
