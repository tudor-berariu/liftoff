import socket
from argparse import ArgumentParser


def main():
    arg_parser = ArgumentParser()
    arg_parser.add_argument("port", type=int, help="Local port to connect to")
    args = arg_parser.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('127.0.0.1', args.port))
        cmd = input('--> ')
        while cmd != "exit":
            sock.sendall((cmd + " END\n").encode('utf-8'))
            answers = sock.recv(2048)
            while not answers.endswith(b' END\n'):
                answers += sock.recv(2048)
            for answer in answers.split(b' END\n'):
                print(answer.decode().strip())
            cmd = input('--> ')

    print("Done!")


if __name__ == "__main__":
    main()
