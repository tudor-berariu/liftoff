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


class TestPrepareCLI:
    def _check_subdirectory_validity_1(self, subdir_path):
        # Check for the presence of another subfolder and .cfg_hash file
        contents = os.listdir(subdir_path)
        subfolders = [
            item for item in contents if os.path.isdir(os.path.join(subdir_path, item))
        ]
        cfg_hash_file = ".__cfg_hash"

        assert (
            len(subfolders) == 1
        ), f"Expected 1 subfolder in {subdir_path}, found {len(subfolders)}"
        assert (
            cfg_hash_file in contents
        ), f"Missing {cfg_hash_file} file in {subdir_path}"

        # Check the subfolder's contents for cfg.yaml and .leaf file
        subfolder_path = os.path.join(subdir_path, subfolders[0])
        subfolder_contents = os.listdir(subfolder_path)
        expected_files = ["cfg.yaml", ".__leaf"]

        for expected_file in expected_files:
            assert (
                expected_file in subfolder_contents
            ), f"Missing {expected_file} in {subfolder_path}"

    def test_prepare_gridsearch_config(self, method_scoped_directory):
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

        # Define the regex pattern for the folder name
        date_pattern = re.compile(r"\d{4}[A-Za-z]{3}\d{2}-\d{6}")

        # Check if the subdirectory name matches the date format
        subdir_name = subdirs[0]
        assert date_pattern.match(
            subdir_name
        ), "Folder name does not match the expected date-time format"

        # Path to the subdirectory
        subdir_path = os.path.join(method_scoped_directory, subdir_name)

        # List all subdirectories in the found subdirectory
        sub_subdirs = [
            d
            for d in os.listdir(subdir_path)
            if os.path.isdir(os.path.join(subdir_path, d))
        ]

        # Check that there are exactly two sub-subdirectories
        assert (
            len(sub_subdirs) == 4
        ), f"Expected 4 subdirectories in {subdir_name}, found {len(sub_subdirs)}"

        assert ".__experiment" in os.listdir(subdir_path)

        for sub_subdir in sub_subdirs:
            sub_subdir_path = os.path.join(subdir_path, sub_subdir)
            self._check_subdirectory_validity_1(sub_subdir_path)
            
    def test_multiple_experiments_long_variable_names_config_prepare(self, method_scoped_directory):

        ### Run liftoff-prepare command
        config_directory = "example_configs_long"
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

        # Define the regex pattern for the folder name
        date_pattern = re.compile(r"\d{4}[A-Za-z]{3}\d{2}-\d{6}")

        # Check if the subdirectory name matches the date format
        subdir_name = subdirs[0]
        assert date_pattern.match(
            subdir_name
        ), "Folder name does not match the expected date-time format"

        # Path to the subdirectory
        subdir_path = os.path.join(method_scoped_directory, subdir_name)

        # List all subdirectories in the found subdirectory
        sub_subdirs = [
            d
            for d in os.listdir(subdir_path)
            if os.path.isdir(os.path.join(subdir_path, d))
        ]

        # Check that there are exactly 4 sub-subdirectories (nr of parameter combinations)
        assert (
            len(sub_subdirs) == 16
        ), f"Expected 16 subdirectories in {subdir_name}, found {len(sub_subdirs)}"

        assert ".__experiment" in os.listdir(subdir_path)

        for sub_subdir in sub_subdirs:
            sub_subdir_path = os.path.join(subdir_path, sub_subdir)
            self._check_subdirectory_validity_1(sub_subdir_path)
