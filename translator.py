import argparse
import logging
import sys

import compiler.compiler as compiler


def translate(source_path, output_path, output_hex_path=None, verbose=False):
    compiler.compile_program(source_path, output_path, output_hex_path=output_hex_path, verbose=verbose)


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(message)s", stream=sys.stdout)
    parser = argparse.ArgumentParser(prog="Translator", description="Translator utility")
    parser.add_argument("source_path")
    parser.add_argument("-o", "--output_path", required=True)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-e", "--output_hex_path", required=False)
    args = parser.parse_args()
    translate(args.source_path, args.output_path, output_hex_path=args.output_hex_path, verbose=args.verbose)


if __name__ == "__main__":
    main()
