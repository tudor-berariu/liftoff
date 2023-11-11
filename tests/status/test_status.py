import pytest
import os
import re
from ..shared.utils import run_cli_command, clean_up_directory

CLEANUP_TESTS_OUTPUTS = False

feature_test_location = os.path.dirname(os.path.realpath(__file__))
shared_resources_location = os.path.join(
    os.path.dirname(feature_test_location), "shared"
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


class TestStatusCLI:
    def _check_unstarted_status(self, status_output):
        # First row check
        expected_headers = ["Total", "Locked", "Done", "Dead", "Progress", "ETL"]
        assert all(header in status_output for header in expected_headers), \
            "Status output does not contain expected headers"

        # Explicitly check the values under each column
        match = re.search(r"example_configs_1\s+4\s+0\s+0\s+0\s+0.000%\s+", status_output)
        assert match, "Status output does not contain expected values for an unstarted experiment"
        

    def test_status_unstarted_experiment(self, method_scoped_directory):
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

        # Run liftoff-status command
        status_command = [
            "liftoff-status",
            "--results-path",
            method_scoped_directory
        ]
        result = run_cli_command(command=status_command, cwd=feature_test_location)

        # Check the output
        self._check_unstarted_status(result.stdout.decode("utf-8"))

        

      
