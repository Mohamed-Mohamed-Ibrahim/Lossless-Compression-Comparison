import heapq
from shared_types import LiteralEvent, MatchEvent, EndEvent
from deflate.deflate import (
    length_extra as _len_extra,
    distance_extra as _dist_extra,
)

def build_huffman_lengths(freq: list[int]) -> list[int]:
    n = len(freq)
    lengths = [0] * n

    heap = []
    for sym, f in enumerate(freq):
        if f > 0:
            heapq.heappush(heap, (f, sym, [sym]))

    if len(heap) == 0:
        return lengths

    if len(heap) == 1:
        _, _, syms = heap[0]
        for s in syms:
            lengths[s] = 1
        return lengths

    while len(heap) > 1:
        f1, m1, s1 = heapq.heappop(heap)
        f2, m2, s2 = heapq.heappop(heap)
        merged_syms = s1 + s2
        merged_freq = f1 + f2
        merged_min = min(m1, m2)
        heapq.heappush(heap, (merged_freq, merged_min, merged_syms))

        for s in s1:
            lengths[s] += 1
        for s in s2:
            lengths[s] += 1

    return lengths

def build_canonical_codes(lengths: list[int]) -> dict[int, str]:
    if not lengths:
        return {}

    count = [0] * 16
    for l in lengths:
        if l > 0:
            count[l] += 1

    count[0] = 0
    next_code = [0] * 16
    code = 0
    for bits in range(1, 16):
        code = (code + count[bits - 1]) << 1
        next_code[bits] = code

    symbol_code: dict[int, str] = {}
    for symbol in range(len(lengths)):
        length = lengths[symbol]
        if length != 0:
            symbol_code[symbol] = format(next_code[length], f"0{length}b")
            next_code[length] += 1

    return symbol_code

class HuffmanEncoder:
    def __init__(self, lit_lengths: list[int], dist_lengths: list[int]):
        self.lit_codes = build_canonical_codes(lit_lengths)
        self.dist_codes = build_canonical_codes(dist_lengths)

    def encode_events(self, events: list) -> str:
        bits = []
        for ev in events:
            if isinstance(ev, LiteralEvent):
                bits.append(self.lit_codes[ev.symbol])

            elif isinstance(ev, MatchEvent):
                bits.append(self.lit_codes[ev.length_symbol])
                if ev.length_extra_bits:
                    bits.append(ev.length_extra_bits)
                bits.append(self.dist_codes[ev.distance_symbol])
                if ev.distance_extra_bits:
                    bits.append(ev.distance_extra_bits)

            elif isinstance(ev, EndEvent):
                bits.append(self.lit_codes[256])

        return "".join(bits)

class HuffmanDecoder:
    def __init__(self, bits: str, lit_lengths: list[int], dist_lengths: list[int]):
        self.bits = bits
        self.pos = 0
        self.lit_table = self._build_decode_table(lit_lengths)
        self.dist_table = self._build_decode_table(dist_lengths)
        self.lit_lengths = lit_lengths
        self.dist_lengths = dist_lengths

    @staticmethod
    def _build_decode_table(lengths: list[int]) -> dict[str, int]:
        codes = build_canonical_codes(lengths)
        return {bits: sym for sym, bits in codes.items()}

    def _read_bits(self, n: int) -> str:
        chunk = self.bits[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def _decode_symbol(self, table: dict[str, int], lengths: list[int]) -> int:
        max_len = max((l for l in lengths if l > 0), default=0)
        prefix = ""
        for _ in range(max_len):
            if self.pos >= len(self.bits):
                raise ValueError("Bitstream exhausted during symbol decode")
            prefix += self.bits[self.pos]
            self.pos += 1
            if prefix in table:
                return table[prefix]
        raise ValueError(f"No valid codeword found (prefix={prefix!r})")

    def decode_events(self) -> list:
        events = []
        while self.pos < len(self.bits):
            sym = self._decode_symbol(self.lit_table, self.lit_lengths)

            if 0 <= sym <= 255:
                events.append(LiteralEvent(sym))

            elif sym == 256:
                events.append(EndEvent())
                break  

            elif 257 <= sym <= 285:
                idx = sym - 257
                n_extra = _len_extra[idx]
                len_extra_bits = self._read_bits(n_extra) if n_extra else ""

                dist_sym = self._decode_symbol(self.dist_table, self.dist_lengths)

                n_dist_extra = _dist_extra[dist_sym]
                dist_extra_bits = self._read_bits(n_dist_extra) if n_dist_extra else ""

                events.append(
                    MatchEvent(sym, len_extra_bits, dist_sym, dist_extra_bits)
                )

            else:
                raise ValueError(f"Invalid literal/length symbol: {sym}")

        return events


if __name__ == "__main__":
    lengths = [0] * 286
    lengths[97] = 3
    lengths[98] = 3
    lengths[99] = 2
    lengths[256] = 2
    lengths[263] = 2

    codes = build_canonical_codes(lengths)
    expected = {99: "00", 256: "01", 263: "10", 97: "110", 98: "111"}
    assert codes == expected, f"Mismatch: {codes} != {expected}"
    print("  ✓ Canonical code table matches spec\n")

    dist_lengths = [0] * 30
    dist_lengths[2] = 1
    dist_codes = build_canonical_codes(dist_lengths)
    assert dist_codes[2] == "0", f"Distance code mismatch: {dist_codes}"
    print(f"  Distance code 2 → '{dist_codes[2]}' ✓\n")
