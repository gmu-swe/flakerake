import csv
import base64
import argparse

# Make pipe work quickly
from signal import signal, SIGPIPE, SIG_DFL

# Ignore SIG_PIPE and don't throw exceptions on it... (http://docs.python.org/library/signal.html)
signal(SIGPIPE, SIG_DFL)


def flake_rake_base64_encode(arg):
    return base64.b64encode(arg.encode('ascii')).decode('ascii')


def flake_rake_base64_decode(arg):
    return base64.b64decode(arg.encode('ascii')).decode('ascii')


def main(args):
    csv_path = args.csv
    output = args.output
    base64_encode_col_arg = args.base64_encode_col
    base64_decode_col_arg = args.base64_decode_col

    with open(csv_path) as csv_fd:
        csv_dict_reader = csv.DictReader(csv_fd)
        rows_operand = list(csv_dict_reader)
        fieldnames = csv_dict_reader.fieldnames

    def base64_encode_col():
        for row in rows_operand:
            row[base64_encode_col_arg] = flake_rake_base64_encode(row[base64_encode_col_arg])

    def base64_decode_col():
        try:
            for row in rows_operand:
                row[base64_decode_col_arg] = flake_rake_base64_decode(row[base64_decode_col_arg])
        except ValueError as e:
            print(f'ERROR: Col {base64_decode_col_arg} might not be base64 encoded')
            print(e.with_traceback())

    if (base64_encode_col_arg):
        base64_encode_col()

    elif (base64_decode_col_arg):
        base64_decode_col()

    with open(output, 'w') as output_fd:
        csv_dict_writer = csv.DictWriter(output_fd, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        csv_dict_writer.writeheader()
        csv_dict_writer.writerows(rows_operand)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Simple csv utility script for peforming operations on FlakeRake produced csvs. '
                    'Supports only a single action at a time.'
    )

    parser.add_argument('--csv', help='Path to FlakeRake csv file to operate upon. Default is stdin',
                        default='/dev/stdin')
    parser.add_argument('-o', '--output', help='Default is stdout', default='/dev/stdout')

    # Actions
    parser.add_argument('--base64_encode_col', help='Must be Col name')
    parser.add_argument('--base64_decode_col', help='Must be Col name')

    main(parser.parse_args())
