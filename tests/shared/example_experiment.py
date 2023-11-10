from liftoff import parse_opts
from argparse import Namespace

def run(opts: Namespace) -> None:
    pass

def main():
    opts = parse_opts()
    run(opts)

if __name__ == "__main__":
    main()