import os
import subprocess
import threading
import shutil

from typing import List

import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logger(name, log_file=None, level=logging.INFO):
    """Set up a logger that logs to the console and optionally to a file."""

    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create a console handler
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # If a log file path is provided, set up file handler
    if log_file is not None:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1024 * 1024 * 5, backupCount=3
        )  # 5MB per file, with 3 backups
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger

def run_cli_command(command: List[str], cwd: str) -> subprocess.CompletedProcess:
    # Run the CLI command and return the output
    return subprocess.run(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    
def run_cli_command_non_blocking(command: List[str], cwd: str):
    """Run the CLI command in a non-blocking manner and return the thread."""
    def target():
        subprocess.run(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )

    thread = threading.Thread(target=target)
    thread.start()
    return thread

def clean_up_directory(directory_path):
    if os.path.exists(directory_path):
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')


