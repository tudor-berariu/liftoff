import os
from liftoff import parse_opts
from argparse import Namespace

import logging
from logging.handlers import RotatingFileHandler


def setup_logger(name, log_file=None, level=logging.INFO):
    """Set up a logger that logs to the console and optionally to a file."""

    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create a console handler
    console_handler = logging.StreamHandler()
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


def run(opts: Namespace) -> None:
    logger = setup_logger(
        opts.full_title, log_file=os.path.join(opts.out_dir, "experiment_log.log")
    )

    result = (opts.a + opts.b) * opts.c

    logger.info(f"Result is {result}")


def main():
    opts = parse_opts()
    run(opts)


if __name__ == "__main__":
    main()
