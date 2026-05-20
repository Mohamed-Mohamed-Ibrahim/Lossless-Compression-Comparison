import os
import sys
import logging
import argparse
from constants.modes import Mode
from deflate.compressor import DeflateCompressor
from range_coding.compressor import RangeCodingCompressor


def get_parser():
    parser = argparse.ArgumentParser(
        description="Data Compressor using range coding or deflate"
    )
    # Range Coding args
    parser.add_argument("-rc", type=str, help="compress a file using range coding")
    parser.add_argument(
        "-rd",
        type=str,
        help="decompress a file using range coding",
    )
    # Deflate args
    parser.add_argument("-c", type=str, help="compress a file using deflate")
    parser.add_argument(
        "-d",
        type=str,
        help="decompress a file using deflate",
    )

    return parser.parse_args()


def configure_logging():
    os.makedirs("log", exist_ok=True)
    logging.basicConfig(
        filename="log/app.log",
        filemode="w",
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def check_file_path(mode, filePath):
    if mode == Mode.RangeCodingDecompressor and not filePath.endswith(".rng"):
        logging.error("Range Coding Decompressed file should end with rng.")
        sys.exit(1)
    if mode == Mode.DeflateDecompressor and not filePath.endswith(".sdfl"):
        logging.error("Deflate Decompressed file should end with sdfl.")
        sys.exit(1)


def main():
    args = get_parser()
    configure_logging()

    mode = None
    filePath = None

    if args.rc != None:
        mode = Mode.RangeCodingCompressor
        filePath = args.rc
    elif args.rd != None:
        mode = Mode.RangeCodingDecompressor
        filePath = args.rd
    elif args.c != None:
        mode = Mode.DeflateCompressor
        filePath = args.c
    elif args.d != None:
        mode = Mode.DeflateDecompressor
        filePath = args.d
    else:
        logging.error("Sorry not supported operation.")
        sys.exit(1)

    check_file_path(mode, filePath)

    with open(filePath, "rb") as file:
        data = file.read()

    try:
        if mode == Mode.RangeCodingCompressor:
            compressor = RangeCodingCompressor()
            compressor.compress(data)
        elif mode == Mode.RangeCodingCompressor:
            decompressor = RangeCodingCompressor()
            decompressor.decompress(data)
        elif mode == Mode.DeflateCompressor:
            compressor = DeflateCompressor()
            compressor.compress(data)
        elif mode == Mode.DeflateDecompressor:
            decompressor = DeflateCompressor()
            decompressor.decompress(data)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")



if __name__ == "__main__":
    main()
