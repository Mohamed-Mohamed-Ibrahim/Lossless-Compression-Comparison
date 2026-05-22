import os
import sys
import logging
import argparse
from constants.modes import Mode
from constants.constants import MAX_FILE_SIZE
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


def check_file_size(filePath):
    size = os.path.getsize(filePath)
    if size > MAX_FILE_SIZE:
        logging.error("Maximum File size allowed is 50 MB.")
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

    try:
        check_file_path(mode, filePath)

        check_file_size(filePath)

        with open(filePath, "rb") as file:
            data = file.read()

        if mode == Mode.RangeCodingCompressor:
            compressor = RangeCodingCompressor()
            compressedData = compressor.compress(data)
            out_path = filePath + ".rng"
            with open(out_path, "wb") as f:
                f.write(compressedData)
        elif mode == Mode.RangeCodingDecompressor:
            decompressor = RangeCodingCompressor()
            decompressedData = decompressor.decompress(data)
            out_path = filePath.rsplit(".rng", 1)[0]
            with open(out_path, "wb") as f:
                f.write(decompressedData)
        elif mode == Mode.DeflateCompressor:
            compressor = DeflateCompressor()
            compressor.compress(data)
            compressedData = compressor.compress(data)
            out_path = filePath + ".sdfl"
            with open(out_path, "wb") as f:
                f.write(compressedData)
        elif mode == Mode.DeflateDecompressor:
            decompressor = DeflateCompressor()
            decompressedData = decompressor.decompress(data)
            out_path = filePath.rsplit(".sdfl", 1)[0]
            with open(out_path, "wb") as f:
                f.write(decompressedData)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
