from template.compressor import Compressor
import numpy as np
import itertools
from .utils import (
    INITIAL_LOW,
    INITIAL_HIGH,
    QUARTER,
    HALF,
    THREE_QUARTER,
    MASK,
    compute_cumulative_ranges,
)


class RangeCodingCompressor(Compressor):
    __slots__ = (
        "low",
        "high",
        "pending_bits",
        "cum_low",
        "cum_high",
        "buf",
        "buf_len",
        "out",
    )

    def __init__(self):
        # Initialize encoder state: full range [0, HIGH], empty bit buffer and output
        self.low = INITIAL_LOW
        self.high = INITIAL_HIGH
        self.pending_bits = 0
        self.buf = 0
        self.buf_len = 0
        self.out = bytearray()


    def emit(self, bit):
        # Accumulate bits into a byte buffer; flush to output when full
        self.buf = (self.buf << 1) | bit
        self.buf_len += 1
        if self.buf_len == 8:
            self.out.append(self.buf)
            self.buf = 0
            self.buf_len = 0


    def emit_with_pending(self, bit):
        # Emit a bit followed by all pending opposite bits (E3 scaling resolution)
        self.emit(bit)
        inv = 1 - bit
        for _ in range(self.pending_bits):
            self.emit(inv)
        self.pending_bits = 0


    def encode_all(self, data):
        # Narrow the range for each symbol (plus EOF 256), applying E1/E2/E3 renormalization
        total = len(data) + 1
        for symbol in itertools.chain(data, (256,)):
            range = self.high - self.low + 1
            low = self.low + range * self.cum_low[symbol] // total
            high = self.low + range * self.cum_high[symbol] // total - 1

            while True:
                if high < HALF:
                    self.emit_with_pending(0)        # E1: both in lower half
                    low = low << 1
                    high = (high << 1) + 1

                elif low >= HALF:
                    self.emit_with_pending(1)        # E2: both in upper half
                    low = (low - HALF) << 1
                    high = ((high - HALF) << 1) + 1

                elif low >= QUARTER and high < THREE_QUARTER:
                    self.pending_bits += 1           # E3: range straddles midpoint, defer bit
                    low = (low - QUARTER) << 1
                    high = ((high - QUARTER) << 1) + 1

                else:
                    break

                self.low, self.high = low & MASK, high & MASK


    def finalize_encoding(self):
        # Flush the final range by emitting one disambiguating bit plus all pending bits
        self.pending_bits += 1

        if self.low < QUARTER:
            self.emit_with_pending(0)
        else:
            self.emit_with_pending(1)

        while self.buf_len != 0:        # Pad last byte with zeros if needed
            self.emit(0)


    def compress(self, data):
        # Build frequency table, encode all symbols, and prepend freq table to bitstream
        freq = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
        freq = np.append(freq, [1])     # Slot 256 = EOF symbol with count 1
        self.cum_low, self.cum_high = compute_cumulative_ranges(freq)
        self.encode_all(data)
        self.finalize_encoding()
        return freq.astype(">u4").tobytes() + self.out