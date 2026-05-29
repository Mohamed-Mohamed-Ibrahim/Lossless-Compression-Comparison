from template.compressor import Compressor
from deflate.deflate import (
    get_lz77_tokens,
    tokens_to_events,
    count_frequencies,
    deflate_decompress,
)
from deflate.huffman import build_huffman_lengths, HuffmanEncoder, HuffmanDecoder
class BitWriter:
    def __init__(self):
        self._bits: list[str] = []

    def write(self, bit_str: str) -> None:
        self._bits.append(bit_str)

    def write_uint(self, value: int, width: int) -> None:
        if width == 0:
            return
        self._bits.append(format(value, f"0{width}b"))

    def finish(self) -> bytes:
        full = "".join(self._bits)
        remainder = len(full) % 8
        if remainder:
            full += "0" * (8 - remainder)
        result = bytearray()
        for i in range(0, len(full), 8):
            result.append(int(full[i : i + 8], 2))
        return bytes(result)


class BitReader:
    def __init__(self, data: bytes):
        self._bits = "".join(format(b, "08b") for b in data)
        self._pos = 0

    def read_uint(self, width: int) -> int:
        if width == 0:
            return 0
        chunk = self._bits[self._pos : self._pos + width]
        if len(chunk) < width:
            raise EOFError("Bitstream ended unexpectedly")
        self._pos += width
        return int(chunk, 2)

    def remaining_bits(self) -> str:
        return self._bits[self._pos :]

def _compute_bw(lengths: list[int]) -> int:
    M = max(lengths, default=0)
    if M == 0:
        return 0
    bit_len = M.bit_length()
    return bit_len


class DeflateCompressor(Compressor):
    def compress(self, data: bytes) -> bytes:
        tokens = get_lz77_tokens(data)

        events = tokens_to_events(tokens)
        lit_freq, dist_freq = count_frequencies(events)

        lit_lengths = build_huffman_lengths(lit_freq)  
        dist_lengths = build_huffman_lengths(dist_freq)

        encoder = HuffmanEncoder(lit_lengths, dist_lengths)

        payload_bits = encoder.encode_events(events)

        bw = BitWriter()

        lit_bw = _compute_bw(lit_lengths)
        bw.write_uint(lit_bw, 4)

        dist_bw = _compute_bw(dist_lengths)
        bw.write_uint(dist_bw, 4)

        for length in lit_lengths: 
            bw.write_uint(length, lit_bw)

        for length in dist_lengths:
            bw.write_uint(length, dist_bw)

        bw.write(payload_bits)

        return bw.finish()

    def decompress(self, data: bytes) -> bytes:
        reader = BitReader(data)

        lit_bw = reader.read_uint(4)
        dist_bw = reader.read_uint(4)

        lit_lengths = [reader.read_uint(lit_bw) for _ in range(286)]
        dist_lengths = [reader.read_uint(dist_bw) for _ in range(30)]

        payload_bits = reader.remaining_bits()
        decoder = HuffmanDecoder(payload_bits, lit_lengths, dist_lengths)
        events = decoder.decode_events()

        return deflate_decompress(events)
