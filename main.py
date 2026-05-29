import os
import logging
import argparse
import time
from constants.modes import Mode
from constants.constants import MAX_FILE_SIZE
from deflate.compressor import DeflateCompressor
from range_coding.compressor import RangeCodingCompressor
from range_coding.decompressor import RangeCodingDecompressor


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


def get_mode_from_args(args):
    mode, filePath = None, None
    if args.rc is not None:
        mode = Mode.RangeCodingCompressor
        filePath = args.rc
    elif args.rd is not None:
        mode = Mode.RangeCodingDecompressor
        filePath = args.rd
    elif args.c is not None:
        mode = Mode.DeflateCompressor
        filePath = args.c
    elif args.d is not None:
        mode = Mode.DeflateDecompressor
        filePath = args.d
    else:
        raise Exception("Sorry not supported operation.")
    return mode, filePath


def check_file_path(mode, filePath):
    if mode == Mode.RangeCodingDecompressor and not filePath.endswith(".rng"):
        raise Exception("Range Coding Decompressed file should end with rng.")
    if mode == Mode.DeflateDecompressor and not filePath.endswith(".sdfl"):
        raise Exception("Deflate Decompressed file should end with sdfl.")


def check_file_size(filePath):
    size = os.path.getsize(filePath)
    if size > MAX_FILE_SIZE:
        raise Exception("Maximum File size allowed is 50 MB.")


def main():
    start = time.time()
    args = get_parser()
    configure_logging()

    mode = None
    filePath = None

    try:
        mode, filePath = get_mode_from_args(args)

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
            decompressor = RangeCodingDecompressor()
            decompressedData = decompressor.decompress(data)
            out_path = filePath.rsplit(".rng", 1)[0]
            with open(out_path, "wb") as f:
                f.write(decompressedData)
        elif mode == Mode.DeflateCompressor:
            compressor = DeflateCompressor()
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

    elapsed_time = time.time() - start
    print(f"Elapsed time : {elapsed_time} seconds")


if __name__ == "__main__":
    main()
