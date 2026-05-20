from enum import Enum

class Mode(Enum):
    RangeCodingCompressor = 1
    RangeCodingDecompressor = 2
    DeflateCompressor = 3
    DeflateDecompressor = 4