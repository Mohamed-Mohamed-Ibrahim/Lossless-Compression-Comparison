from template.decompressor import Decompressor
import numpy as np
from bitarray import bitarray
from .utils import (
    INITIAL_LOW,
    INITIAL_HIGH,
    QUARTER,
    HALF,
    THREE_QUARTER,
    MASK,
    compute_cumulative_ranges,
)


class RangeCodingDecompressor(Decompressor):
    __slots__ = ("low", "high", "total", "pos", "code", "cum_low", "cum_high", "bits")

    def __init__(self):
        # Initialize decoder state: full range [0, HIGH], code word and bit position at 0
        self.low = INITIAL_LOW
        self.high = INITIAL_HIGH
        self.pos = 0
        self.code = 0


    def read_bit(self):
        # Return the next bit from the bitstream, or 0 once the stream is exhausted
        if self.pos < len(self.bits):
            b = self.bits[self.pos]
            self.pos += 1
            return b
        return 0


    def initialize_code(self):
        # Prime the code register with the first 32 bits of the bitstream
        for _ in range(32):
            self.code = (self.code << 1) | self.read_bit()


    def find_matched_symbol(self, value):
        # Linear scan to find the symbol whose cumulative range contains value
        for i in range(257):
            if value >= self.cum_low[i] and value < self.cum_high[i]:
                return i


    def decode_symbol(self):
        # Map current code word back to a scaled value, then locate its symbol
        range = self.high - self.low + 1
        value = ((self.code - self.low + 1) * self.total - 1) // range
        symbol = self.find_matched_symbol(value)

        # Narrow the range to the matched symbol's interval, mirroring the encoder
        low = self.low + range * self.cum_low[symbol] // self.total
        high = self.low + range * self.cum_high[symbol] // self.total - 1
        code = self.code

        # Renormalize with E1/E2/E3 steps, pulling in new bits to keep code in sync
        while True:
            if high < HALF:
                low, high, code = (        # E1: both in lower half
                    low << 1,
                    (high << 1) + 1,
                    (code << 1) | self.read_bit(),
                )

            elif low >= HALF:
                low, high, code = (        # E2: both in upper half
                    (low - HALF) << 1,
                    ((high - HALF) << 1) + 1,
                    ((code - HALF) << 1) | self.read_bit(),
                )

            elif low >= QUARTER and high < THREE_QUARTER:
                low, high, code = (        # E3: range straddles midpoint
                    (low - QUARTER) << 1,
                    ((high - QUARTER) << 1) + 1,
                    ((code - QUARTER) << 1) | self.read_bit(),
                )

            else:
                break

            self.low, self.high, self.code = low & MASK, high & MASK, code & MASK

        return symbol


    def decompress(self, compressed_data):
        # Parse the prepended freq table (257 × 4 bytes), then load the remaining bits
        self.bits = bitarray()
        freq = np.frombuffer(compressed_data[:1028], dtype=">u4")
        freq = freq.astype(object) 
        self.bits.frombytes(compressed_data[1028:])

        self.total = int(np.sum(freq))     # Total symbol count drives range scaling
        self.cum_low, self.cum_high = compute_cumulative_ranges(freq)
        self.initialize_code()

        # Decode total-1 symbols (excludes the EOF entry added during compression)
        data = bytearray()
        for _ in range(self.total - 1):
            data.append(self.decode_symbol())

        return data