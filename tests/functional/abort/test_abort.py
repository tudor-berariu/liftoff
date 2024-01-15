import pytest
import os
import re
import time
import psutil
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


class TestAbortCLI:
    def test_multiple_experiments_abort(self, method_scoped_directory):
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

        time.sleep(2)  # A bit of delay to let the processes start

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

        # Extract the parent process ID
        parent_pid_pattern = r"\s*(\d+)\s+::"
        parent_pid_match = re.search(parent_pid_pattern, output, re.MULTILINE)
        assert parent_pid_match, f"Parent process ID not found in the output, got output {output}"
        parent_pid = int(parent_pid_match.group(1))

        # Abort the parent process ID
        abort_command = [
            "liftoff-abort",
            str(parent_pid),
            "--results-path",
            method_scoped_directory,
            "--skip-confirmation",
        ]
        abort_process = run_cli_command(
            command=abort_command,
            cwd=feature_test_location,
        )

        assert (
            abort_process.returncode == 0
        ), "Abort command did not execute successfully, got return code:\n" + str(
            abort_process.returncode
        )

        abort_stdout = abort_process.stdout.decode()
        success_message = "The eagle is down! Mission accomplished."
        assert success_message in abort_stdout, (
            "Abort command did not print the expected success message, got:\n"
            + abort_stdout
        )
        
        time.sleep(1)
        
        # Check that the parent process is no longer running
        try:
            psutil.Process(parent_pid)
            raise AssertionError("Parent process is still running after abort")
        except psutil.NoSuchProcess:
            pass  # Process is not running, which is expected

        # Check that liftoff-procs returns 'No running liftoff processes.'
        completed_process = run_cli_command(
            command=["liftoff-procs"],
            cwd=feature_test_location,
        )
        output_after_abort = completed_process.stdout.decode()
        assert (
            no_processes_msg in output_after_abort
        ), "There are still processes running after abort"
