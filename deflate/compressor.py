from template import Compressor
from deflate.deflate import (
    get_lz77_tokens,
    tokens_to_events,
    count_frequencies,
    deflate_decompress,
)

class DeflateCompressor(Compressor):
    def compress(self, data: bytes) -> bytes:
        tokens = get_lz77_tokens(data)

        events = tokens_to_events(tokens)

        lit_freq, dist_freq = count_frequencies(events)

    def decompress(self, data: bytes) -> bytes:
        pass
