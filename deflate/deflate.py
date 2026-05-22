# deflate.py
# ─────────────────────────────────────────────────────────────────
# Stage 2 of the DEFLATE pipeline.
#
# Compression  : tokens_to_events(tokens)  → list of events
# Decompression: deflate_decompress(events) → bytes
#
# Also exports count_frequencies() for Huffman.
# ─────────────────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared_types import Literal, Match, LiteralEvent, MatchEvent, EndEvent


# ══════════════════════════════════════════════════════════════════
# Lookup tables 
# ══════════════════════════════════════════════════════════════════

length_base = [
    3, 4, 5, 6, 7, 8, 9, 10,
    11, 13, 15, 17,
    19, 23, 27, 31,
    35, 43, 51, 59,
    67, 83, 99, 115,
    131, 163, 195, 227,
    258                         # index 28 → symbol 285, exact value only
]

length_extra = [
    0, 0, 0, 0, 0, 0, 0, 0,
    1, 1, 1, 1,
    2, 2, 2, 2,
    3, 3, 3, 3,
    4, 4, 4, 4,
    5, 5, 5, 5,
    0                           # index 28 → 0 extra bits
]

distance_base = [
    1, 2, 3, 4,
    5, 7,
    9, 13,
    17, 25,
    33, 49,
    65, 97,
    129, 193,
    257, 385,
    513, 769,
    1025, 1537,
    2049, 3073,
    4097, 6145,
    8193, 12289,
    16385, 24577
]

distance_extra = [
    0, 0, 0, 0,
    1, 1,
    2, 2,
    3, 3,
    4, 4,
    5, 5,
    6, 6,
    7, 7,
    8, 8,
    9, 9,
    10, 10,
    11, 11,
    12, 12,
    13, 13
]


# ══════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════

def encode_length(length: int) -> tuple[int, str]:
    """
    Map a match length (3..258) to (length_symbol, extra_bits_string).

    Length 258 is a special case: it maps ONLY to symbol 285.
    Without this guard, the loop would match it to symbol 284
    because 227 + 2^5 = 259 > 258.
    """
    assert 3 <= length <= 258, f"Invalid length: {length}"

    if length == 258:               # ← special case, must come first
        return 285, ''

    for i in range(len(length_base) - 1):   # skip last entry (index 28)
        base     = length_base[i]
        n_extra  = length_extra[i]
        if base <= length < base + (1 << n_extra):
            extra_bits = format(length - base, f'0{n_extra}b') if n_extra else ''
            return 257 + i, extra_bits

    raise ValueError(f"Length {length} not found in table")


def encode_distance(distance: int) -> tuple[int, str]:
    """
    Map a match distance (1..32768) to (distance_symbol, extra_bits_string).
    """
    assert 1 <= distance <= 32768, f"Invalid distance: {distance}"

    for i in range(len(distance_base)):
        base    = distance_base[i]
        n_extra = distance_extra[i]
        if base <= distance < base + (1 << n_extra):
            extra_bits = format(distance - base, f'0{n_extra}b') if n_extra else ''
            return i, extra_bits

    raise ValueError(f"Distance {distance} not found in table")


def decode_length(length_symbol: int, extra_bits_string: str) -> int:
    """Map (length_symbol, extra_bits_string) back to the original length."""
    i = length_symbol - 257
    base    = length_base[i]
    n_extra = length_extra[i]
    if n_extra == 0:
        return base
    return base + int(extra_bits_string, 2)


def decode_distance(distance_symbol: int, extra_bits_string: str) -> int:
    """Map (distance_symbol, extra_bits_string) back to the original distance."""
    base    = distance_base[distance_symbol]
    n_extra = distance_extra[distance_symbol]
    if n_extra == 0:
        return base
    return base + int(extra_bits_string, 2)


def _lz77_copy(buf: bytearray, length: int, distance: int) -> None:
    """
    Copy `length` bytes into `buf` starting from `distance` bytes back.
    Must be byte-by-byte to correctly handle overlapping matches
    (e.g. distance=1 repeats the last byte `length` times).
    """
    start = len(buf) - distance
    for i in range(length):
        buf.append(buf[start + i])


# ══════════════════════════════════════════════════════════════════
# Public API — compression side
# ══════════════════════════════════════════════════════════════════

def tokens_to_events(tokens: list) -> list:
    """
    Stage 2 encoding.
    Convert a list of Literal/Match tokens (from LZ77 teammate)
    into a list of LiteralEvent/MatchEvent/EndEvent (for Huffman teammate).
    """
    events = []

    for token in tokens:
        if isinstance(token, Literal):
            events.append(LiteralEvent(token.byte))

        elif isinstance(token, Match):
            len_sym,  len_bits  = encode_length(token.length)
            dist_sym, dist_bits = encode_distance(token.distance)
            events.append(MatchEvent(len_sym, len_bits, dist_sym, dist_bits))

        else:
            raise TypeError(f"Unknown token type: {type(token)}")

    events.append(EndEvent())   # always terminate the stream
    return events


def count_frequencies(events: list) -> tuple[list, list]:
    """
    Count Huffman symbol frequencies.
    Called by the Huffman teammate (or by us before handing off).

    Returns:
        lit_freq  — list[286]  frequencies for literal/length symbols 0–285
        dist_freq — list[30]   frequencies for distance symbols 0–29
    """
    lit_freq  = [0] * 286
    dist_freq = [0] * 30

    for ev in events:
        if isinstance(ev, LiteralEvent):
            lit_freq[ev.symbol] += 1
        elif isinstance(ev, MatchEvent):
            lit_freq[ev.length_symbol]   += 1
            dist_freq[ev.distance_symbol] += 1
        elif isinstance(ev, EndEvent):
            lit_freq[256] += 1

    return lit_freq, dist_freq


# ══════════════════════════════════════════════════════════════════
# Public API — decompression side
# ══════════════════════════════════════════════════════════════════

def deflate_decompress(events: list) -> bytes:
    """
    Stage 2 decoding.
    Convert a list of events (produced by Huffman teammate's decoder)
    back into the original byte sequence.
    Stops at the first EndEvent.
    """
    buf = bytearray()

    for ev in events:
        if isinstance(ev, LiteralEvent):
            buf.append(ev.symbol)

        elif isinstance(ev, MatchEvent):
            length   = decode_length(ev.length_symbol,   ev.length_extra_bits)
            distance = decode_distance(ev.distance_symbol, ev.distance_extra_bits)
            _lz77_copy(buf, length, distance)

        elif isinstance(ev, EndEvent):
            break   # trailing padding bits after this are irrelevant

    return bytes(buf)


# ══════════════════════════════════════════════════════════════════
# Self-tests  (run with:  python deflate.py)
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # ── encode_length ──────────────────────────────────────────
    assert encode_length(3)   == (257, ''),  "length 3"
    assert encode_length(9)   == (263, ''),  "length 9"
    assert encode_length(20)  == (269, '01'),"length 20"
    assert encode_length(258) == (285, ''),  "length 258"
    print("encode_length        : OK")

    # ── encode_distance ────────────────────────────────────────
    assert encode_distance(1) == (0, ''),  "distance 1"
    assert encode_distance(3) == (2, ''),  "distance 3"
    assert encode_distance(6) == (4, '1'), "distance 6"
    print("encode_distance      : OK")

    # ── round-trip length ──────────────────────────────────────
    for L in range(3, 259):
        sym, bits = encode_length(L)
        assert decode_length(sym, bits) == L, f"length round-trip failed for {L}"
    print("length round-trip    : OK (3..258)")

    # ── round-trip distance ────────────────────────────────────
    for D in [1, 2, 3, 4, 5, 6, 7, 8, 100, 1000, 10000, 32768]:
        sym, bits = encode_distance(D)
        assert decode_distance(sym, bits) == D, f"distance round-trip failed for {D}"
    print("distance round-trip  : OK")

    # ── spec worked example ────────────────────────────────────
    tokens = [Literal(97), Literal(98), Literal(99), Match(length=9, distance=3)]
    events = tokens_to_events(tokens)

    expected_events = [
        LiteralEvent(97), LiteralEvent(98), LiteralEvent(99),
        MatchEvent(263, '', 2, ''), EndEvent()
    ]
    for a, b in zip(events, expected_events):
        assert repr(a) == repr(b), f"\nGot:      {a}\nExpected: {b}"
    print("tokens_to_events     : OK")

    result = deflate_decompress(events)
    assert result == b'abcabcabcabc', f"Got {result}"
    print("deflate_decompress   : OK  (spec example)")

    # ── overlapping match ──────────────────────────────────────
    events2 = tokens_to_events([Literal(97), Match(length=9, distance=1)])
    assert deflate_decompress(events2) == b'aaaaaaaaaa'
    print("overlapping match    : OK")

    # ── count_frequencies ──────────────────────────────────────
    lit_freq, dist_freq = count_frequencies(events)
    assert lit_freq[97]  == 1
    assert lit_freq[98]  == 1
    assert lit_freq[99]  == 1
    assert lit_freq[263] == 1
    assert lit_freq[256] == 1
    assert dist_freq[2]  == 1
    print("count_frequencies    : OK")

    print("\n✓ All tests passed.")
