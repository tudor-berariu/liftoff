import os
import sys
from liftoff import parse_opts
from argparse import Namespace
import time

functional_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(functional_dir)

from shared_test_resources.utils import setup_logger


def run(opts: Namespace) -> None:
    logger = setup_logger(
        opts.full_title, log_file=os.path.join(opts.out_dir, "experiment_log.log")
    )

    time.sleep(100)
    result = (opts.a + opts.b) * opts.c

    logger.info(f"Result is {result}")
    
    return True


def main():
    opts = parse_opts()
    run(opts)


if __name__ == "__main__":
    main()
