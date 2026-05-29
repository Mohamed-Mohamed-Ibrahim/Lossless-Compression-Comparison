# ── LZ77 Tokens (produced by LZ77 , consumed by DEFLATE) ──

class Literal:
    """A single raw byte that could not be matched."""
    def __init__(self, byte: int):
        self.byte = byte

    def __repr__(self):
        return f"Literal({self.byte})"


class Match:
    """A back-reference: copy `length` bytes from `distance` bytes ago."""
    def __init__(self, length: int, distance: int):
        self.length = length
        self.distance = distance

    def __repr__(self):
        return f"Match(length={self.length}, distance={self.distance})"


# ── DEFLATE Events (produced by DEFLATE, consumed by Huffman) ──

class LiteralEvent:
    """
    A literal byte symbol ready for Huffman coding.
    symbol is an integer 0–255.
    """
    def __init__(self, symbol: int):
        self.symbol = symbol

    def __repr__(self):
        return f"LiteralEvent({self.symbol})"


class MatchEvent:
    """
    A match converted into Huffman symbols + raw extra bit strings.

    length_symbol    : int,  range 257–285
    length_extra_bits: str,  e.g. '01'  (empty string if no extra bits)
    distance_symbol  : int,  range 0–29
    distance_extra_bits: str, e.g. '1'  (empty string if no extra bits)
    """
    def __init__(self,
                 length_symbol: int,
                 length_extra_bits: str,
                 distance_symbol: int,
                 distance_extra_bits: str):
        self.length_symbol = length_symbol
        self.length_extra_bits = length_extra_bits
        self.distance_symbol = distance_symbol
        self.distance_extra_bits = distance_extra_bits

    def __repr__(self):
        return (f"MatchEvent({self.length_symbol}, '{self.length_extra_bits}', "
                f"{self.distance_symbol}, '{self.distance_extra_bits}')")


class EndEvent:
    """
    End-of-block marker. Always the last event in a stream.
    symbol is always 256 (the DEFLATE end-of-block symbol).
    """
    def __init__(self):
        self.symbol = 256

    def __repr__(self):
        return "EndEvent(256)"
