"""Warning: these tests seem to sometimes fail,
probably due to race conditions."""

import pytest
import os
import re
import time
from ..shared_test_resources.utils import (
    run_cli_command,
    clean_up_directory,
    run_cli_command_non_blocking,
)

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
    def test_multiple_experiments_procs_half_procs(self, method_scoped_directory):
        """WARNING: this can detect other liftoff processes, make sure to run
        each test independently.
        """
        
        ### Run liftoff-prepare command
        config_directory = "example_configs_1"
        config_folder_path = os.path.join(shared_resources_location, config_directory)

        # This should generate 4 subexperiments
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

        script_name = "example_experiment.py"
        exp_path = os.path.join(method_scoped_directory, subdirs[0])

        command = [
            "liftoff",
            script_name,
            exp_path,
            "--procs-no",
            "2",
        ]
        liftoff_thread = run_cli_command_non_blocking(
            command=command,
            cwd=feature_test_location,
        )

        time.sleep(4)  # A bit of delay to let the processes start

        # Extract the experiment name from the method_scoped_directory
        experiment_name_pattern = os.path.basename(exp_path)
        
        # Regex patterns for different levels
        top_level_pattern = rf"{re.escape(experiment_name_pattern)}"
        mid_level_pattern = rf"\n +\d+ :: [\w-]+ :: 2 running"
        lowest_level_pattern = r"\n {6}- \d+ :: [\w\/]+"

        ## Check that there are 2 processes running, and they are shown
        command = ["liftoff-procs"]
        completed_process = run_cli_command(
            command=command,
            cwd=feature_test_location,
        )

        assert (
            completed_process.returncode == 0
        ), "Liftoff command did not execute successfully"

        # Decode the standard output to a string for regex matching
        output = completed_process.stdout.decode()

        no_processes_msg = "No running liftoff processes."
        if no_processes_msg in output:
            raise AssertionError("There does not seem to be any process running.")

        # Perform regex search for each level
        top_level_match = re.search(top_level_pattern, output)
        mid_level_match = re.search(mid_level_pattern, output)
        lowest_level_match = re.findall(lowest_level_pattern, output)

        # Assert that each pattern matches
        assert (
            top_level_match is not None
        ), "Top level output does not match the expected format"
        assert (
            mid_level_match is not None
        ), "Mid level output does not match the expected format"

        # Assert that there are 2 matches for the lowest level
        assert (
            len(lowest_level_match) == 2
        ), "Lowest level output does not match the expected format or not exactly 2 sub-experiments found"
        
        # Wait for the 2nd round of processes to start, and check that again we find 2 processes
        time.sleep(9)
        
        ## Check that there are 2 processes running, and they are shown
        command = ["liftoff-procs"]
        completed_process = run_cli_command(
            command=command,
            cwd=feature_test_location,
        )

        assert (
            completed_process.returncode == 0
        ), "Liftoff command did not execute successfully"

        # Decode the standard output to a string for regex matching
        output = completed_process.stdout.decode()

        no_processes_msg = "No running liftoff processes."
        if no_processes_msg in output:
            raise AssertionError("There does not seem to be any process running.")

        # Perform regex search for each level
        top_level_match = re.search(top_level_pattern, output)
        mid_level_match = re.search(mid_level_pattern, output)
        lowest_level_match = re.findall(lowest_level_pattern, output)

        # Assert that each pattern matches
        assert (
            top_level_match is not None
        ), "Top level output does not match the expected format"
        assert (
            mid_level_match is not None
        ), "Mid level output does not match the expected format"

        # Assert that there are 2 matches for the lowest level
        assert (
            len(lowest_level_match) == 2
        ), "Lowest level output does not match the expected format or not exactly 2 sub-experiments found"

        
        # Poll for a certain duration to check if the thread has completed
        max_wait_seconds = 15  # Maximum seconds to wait for the thread to finish
        poll_interval_seconds = 1  # Seconds to wait between checks

        elapsed_seconds = 0
        while liftoff_thread.is_alive() and elapsed_seconds < max_wait_seconds:
            time.sleep(poll_interval_seconds)
            elapsed_seconds += poll_interval_seconds

        if liftoff_thread.is_alive():
            raise TimeoutError(
                "Liftoff command did not finish within the expected time."
            )
        else:
            command = ["liftoff-procs"]
            completed_process = run_cli_command(
                command=command,
                cwd=feature_test_location,
            )

            # Ensure the command execution was successful
            assert (
                completed_process.returncode == 0
            ), "Liftoff command did not execute successfully"

            # Decode the standard output to a string for regex matching
            output = completed_process.stdout.decode()

            assert (
                no_processes_msg in output
            ), "There are still running liftoff processes"
            
    def test_multiple_experiments_procs(self, method_scoped_directory):
        """WARNING: this can detect other liftoff processes, make sure to run
        each test independently.
        """
        
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

        script_name = "example_experiment.py"
        exp_path = os.path.join(method_scoped_directory, subdirs[0])

        command = [
            "liftoff",
            script_name,
            exp_path,
            "--procs-no",
            "4",
        ]
        liftoff_thread = run_cli_command_non_blocking(
            command=command,
            cwd=feature_test_location,
        )

        time.sleep(3)  # A bit of delay to let the processes start

        ## Check that there are 4 processes running, and they are shown
        command = ["liftoff-procs"]
        completed_process = run_cli_command(
            command=command,
            cwd=feature_test_location,
        )

        assert (
            completed_process.returncode == 0
        ), "Liftoff command did not execute successfully"

        # Decode the standard output to a string for regex matching
        output = completed_process.stdout.decode()

        no_processes_msg = "No running liftoff processes."
        if no_processes_msg in output:
            raise AssertionError("There does not seem to be any process running.")

        # Extract the experiment name from the method_scoped_directory
        experiment_name_pattern = os.path.basename(exp_path)

        # Regex patterns for different levels
        top_level_pattern = rf"{re.escape(experiment_name_pattern)}"
        mid_level_pattern = rf"\n +\d+ :: [\w-]+ :: 4 running"
        lowest_level_pattern = r"\n {6}- \d+ :: [\w\/]+"

        # Perform regex search for each level
        top_level_match = re.search(top_level_pattern, output)
        mid_level_match = re.search(mid_level_pattern, output)
        lowest_level_match = re.findall(lowest_level_pattern, output)

        # Assert that each pattern matches
        assert (
            top_level_match is not None
        ), "Top level output does not match the expected format"
        assert (
            mid_level_match is not None
        ), "Mid level output does not match the expected format"

        # Assert that there are 4 matches for the lowest level
        assert (
            len(lowest_level_match) == 4
        ), "Lowest level output does not match the expected format or not exactly 4 sub-experiments found"

        # Poll for a certain duration to check if the thread has completed
        max_wait_seconds = 15  # Maximum seconds to wait for the thread to finish
        poll_interval_seconds = 1  # Seconds to wait between checks

        elapsed_seconds = 0
        while liftoff_thread.is_alive() and elapsed_seconds < max_wait_seconds:
            time.sleep(poll_interval_seconds)
            elapsed_seconds += poll_interval_seconds

        if liftoff_thread.is_alive():
            raise TimeoutError(
                "Liftoff command did not finish within the expected time."
            )
        else:
            command = ["liftoff-procs"]
            completed_process = run_cli_command(
                command=command,
                cwd=feature_test_location,
            )

            # Ensure the command execution was successful
            assert (
                completed_process.returncode == 0
            ), "Liftoff command did not execute successfully"

            # Decode the standard output to a string for regex matching
            output = completed_process.stdout.decode()

            assert (
                no_processes_msg in output
            ), "There are still running liftoff processes"
