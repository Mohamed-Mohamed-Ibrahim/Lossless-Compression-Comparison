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
from collections import defaultdict

from constants.constants import WINDOW_SIZE, MIN_MATCH, MAX_MATCH, MAX_CANDIDATES


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
# Public API — (LZ77 Tokens Generateion)
# ══════════════════════════════════════════════════════════════════
def get_lz77_tokens(data: bytes) -> list:
    tokens = []
    table = defaultdict(list) 
    i = 0
    data_length = len(data)

    while i < data_length:

        if i + MIN_MATCH > data_length:
            tokens.append(Literal(data[i]))
            i += 1
            continue 
        
        key = data[i : i+3]
        best_length = 0
        best_distance = 0
        candidates_checked = 0
        
        for candidate_pos in table[key][::-1]:
            distance = i - candidate_pos
            
            if distance > WINDOW_SIZE or candidates_checked >= MAX_CANDIDATES:
                break
            
            length = 0
            while (i + length < data_length and length < MAX_MATCH and data[i + length] == data[candidate_pos + length]):
                length += 1
        
            if length > best_length:
                best_length = length
                best_distance = distance

            candidates_checked += 1
            
        if best_length >= MIN_MATCH:
            tokens.append(Match(best_length, best_distance))
            
            for k in range(best_length):
                pos = i + k
                if pos + 3 <= data_length:
                    table[data[pos : pos+3]].append(pos)
            
            i += best_length
        
        else:
            tokens.append(Literal(data[i]))
            table[key].append(i)
            i += 1
            
    return tokens

# ══════════════════════════════════════════════════════════════════
# Public API — (LZ77 Decompression)
# ══════════════════════════════════════════════════════════════════

def lz77_decompress(tokens: list) -> bytes:
    buffer = bytearray()
    
    for token in tokens:
        if isinstance(token, Literal):
            buffer.append(token.byte)
            
        elif isinstance(token, Match):
            start_index = len(buffer) - token.distance
            
            for i in range(token.length):
                byte_to_copy = buffer[start_index + i]
                buffer.append(byte_to_copy)
                
    return bytes(buffer)


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

# ══════════════════════════════════════════════════════════════════
# LZ77 Tests
# ══════════════════════════════════════════════════════════════════

def run_lz77_tests():
    print("--- Running LZ77 Tests ---\n")
    all_passed = True

    def check(test_num, description, original, tokens, reconstructed):
        passed = original == reconstructed
        print(f"Test {test_num}: {description}")
        print(f"  Original:      {original}")
        print(f"  Tokens:")
        for t in tokens:
            print(f"    {t}")
        print(f"  Reconstructed: {reconstructed}")
        print(f"  Pass?          {passed}\n")
        return passed

    # ── Test 1: Project worked example (Section 9.2) ──────────────
    data = b'abcabcabcabc'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(1, "Project worked example", data, tokens, recon)

    # ── Test 2: Overlapping match (Section 4.5) ───────────────────
    data = b'aaaaaaaaaa'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(2, "Overlapping match", data, tokens, recon)

    # ── Test 3: Empty input ───────────────────────────────────────
    data = b''
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(3, "Empty input", data, tokens, recon)

    # ── Test 4: Single byte ───────────────────────────────────────
    data = b'A'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(4, "Single byte (must be Literal)", data, tokens, recon)

    # ── Test 5: Two bytes (below MIN_MATCH, must be literals) ─────
    data = b'AB'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(5, "Two bytes - below MIN_MATCH, all literals", data, tokens, recon)

    # ── Test 6: No repetition (all literals) ─────────────────────
    data = b'abcdefghij'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(6, "No repetition - all literals expected", data, tokens, recon)

    # ── Test 7: Exact MIN_MATCH length (length=3) ─────────────────
    data = b'xyzxyz'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    # Must contain a Match(length=3, distance=3)
    has_match = any(isinstance(t, Match) and t.length == 3 for t in tokens)
    passed = (data == recon) and has_match
    print(f"Test 7: Exact MIN_MATCH=3 triggers a match")
    print(f"  Original:      {data}")
    print(f"  Tokens:")
    for t in tokens: print(f"    {t}")
    print(f"  Reconstructed: {recon}")
    print(f"  Has Match(length=3)? {has_match}")
    print(f"  Pass?          {passed}\n")
    all_passed &= passed

    # ── Test 8: Length below MIN_MATCH should NOT produce match ───
    data = b'xyxy'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    # 'xy' repeated - only 2 bytes match so no Match token allowed
    has_illegal_match = any(isinstance(t, Match) and t.length < 3 for t in tokens)
    passed = (data == recon) and not has_illegal_match
    print(f"Test 8: Length < MIN_MATCH must not emit a Match token")
    print(f"  Original:      {data}")
    print(f"  Tokens:")
    for t in tokens: print(f"    {t}")
    print(f"  Reconstructed: {recon}")
    print(f"  Has illegal Match (length<3)? {has_illegal_match}")
    print(f"  Pass?          {passed}\n")
    all_passed &= passed

    # ── Test 9: MAX_MATCH cap (length must not exceed 258) ────────
    data = bytes([65] * 300)  # 300 'A's
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    max_len = max((t.length for t in tokens if isinstance(t, Match)), default=0)
    passed = (data == recon) and (max_len <= 258)
    print(f"Test 9: MAX_MATCH cap - no match length > 258")
    print(f"  Original:      300 x 'A'")
    print(f"  Max match length found: {max_len}")
    print(f"  Reconstructed matches original? {data == recon}")
    print(f"  Pass?          {passed}\n")
    all_passed &= passed

    # ── Test 10: Distance must not exceed WINDOW_SIZE=32768 ───────
    # Two identical 3-byte sequences separated by exactly WINDOW_SIZE bytes
    data = b'abc' + bytes(32768) + b'abc'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    max_dist = max((t.distance for t in tokens if isinstance(t, Match)), default=0)
    passed = (data == recon) and (max_dist <= 32768)
    print(f"Test 10: Distance must not exceed WINDOW_SIZE=32768")
    print(f"  Max distance found: {max_dist}")
    print(f"  Reconstructed matches original? {data == recon}")
    print(f"  Pass?          {passed}\n")
    all_passed &= passed

    # ── Test 11: Multiple non-overlapping matches ─────────────────
    data = b'helloWorldhelloWorld'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(11, "Multiple matches - helloWorldhelloWorld", data, tokens, recon)

    # ── Test 12: Binary data (non-text bytes) ────────────────────
    data = bytes([0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3])
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(12, "Binary data with repetition", data, tokens, recon)

    # ── Test 13: All zeros ────────────────────────────────────────
    data = bytes(50)
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    all_passed &= check(13, "All zero bytes", data, tokens, recon)

    # ── Test 14: Prefer smaller distance on equal match length ────
    # 'abc' appears at pos 0 and pos 3, current pos is 6
    # Both give length=3, should prefer distance=3 (closer)
    data = b'abcabcabc'
    tokens = get_lz77_tokens(data)
    recon = lz77_decompress(tokens)
    # Find the last match - it should prefer distance=3 over distance=6
    matches = [t for t in tokens if isinstance(t, Match)]
    preferred_dist = all(m.distance <= 6 for m in matches)
    passed = (data == recon) and preferred_dist
    print(f"Test 14: Prefer smaller distance on equal match length")
    print(f"  Original:      {data}")
    print(f"  Tokens:")
    for t in tokens: print(f"    {t}")
    print(f"  Reconstructed: {recon}")
    print(f"  Pass?          {passed}\n")
    all_passed &= passed

    # ── Final Result ──────────────────────────────────────────────
    print("=" * 50)
    print(f"All Tests Passed: {all_passed}")
    print("=" * 50)

if __name__ == "__main__":
    run_lz77_tests()