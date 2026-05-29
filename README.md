# Compression-Comparison-Range-Coding-vs-DEFLATE

A comparison of two lossless compression algorithms: **Range Coding** and a simplified **DEFLATE** implementation.

---

## 1. Range Coding Implementation

Range coding is an entropy coder that encodes a sequence of symbols by narrowing down a numeric range based on each symbol's cumulative probability. The implementation:

1. Computes symbol frequencies from the input to build a probability model.
2. Encodes the input by iteratively subdividing the range `[low, high)` according to cumulative frequencies.
3. Writes the frequency table to the output file header, followed by the encoded range value.

The decoder reads the frequency table, reconstructs the probability model, and reverses the range subdivision to recover the original symbols.

---

## 2. Simplified DEFLATE Implementation

The simplified DEFLATE compressor combines **LZ77** back-reference matching with **canonical Huffman coding**:

1. **Stage 1 – LZ77**: Scans the input for repeated substrings and emits a stream of `LiteralEvent` and `MatchEvent` tokens.
2. **Stage 2 – Event Mapping**: Converts lengths and distances to their DEFLATE symbol indices (with extra bits where needed).
3. **Stage 3 – Frequency Count**: Tallies frequencies of all literal/length and distance symbols.
4. **Stage 4 – Huffman Coding**: Builds canonical Huffman codes from the frequency tables.
5. **Stage 5 – Output**: Writes the custom header followed by the Huffman-coded payload.

The decompressor reads the header to reconstruct the Huffman trees, then decodes the payload symbol by symbol.

---

## 3. File Formats

### Range Coding (`.rng`)

| Field | Size | Description |
|---|---|---|
| `NUM_SYMBOLS` | 4 bytes | Number of distinct symbols |
| `SYMBOL_TABLE` | `NUM_SYMBOLS × 5` bytes | Each entry: 1-byte symbol + 4-byte frequency |
| `ORIGINAL_SIZE` | 4 bytes | Original file length in bytes |
| `ENCODED_VALUE` | variable | The final range-coded integer |

### Simplified DEFLATE (`.sdfl`)

| Field | Size | Description |
|---|---|---|
| `LIT_BW` | 4 bits | Bit-width for literal/length code lengths |
| `DIST_BW` | 4 bits | Bit-width for distance code lengths |
| `LIT_TABLE` | `286 × LIT_BW` bits | Code lengths for symbols 0–285 |
| `DIST_TABLE` | `30 × DIST_BW` bits | Code lengths for symbols 0–29 |
| `PAYLOAD` | variable | Huffman-coded data plus raw extra bits |

---

## 4. Compression Results

| File | Original Size | DEFLATE Size | DEFLATE Ratio | Range Size | Range Ratio | Best Method |
|---|---|---|---|---|---|---|
| `01_small_text.txt` | 190 B | ~260 B | 1.3684 | ~1,135 B | 5.9737 | — (both expand) |
| `02_large_text.txt` | 19,716 B | ~4,620 B | 0.2342 | ~11,950 B | 0.6060 | **DEFLATE** |
| `03_repeated.txt` | 3,559 B | ~151 B | 0.0424 | ~2,634 B | 0.7398 | **DEFLATE** |
| `04_source_code.py` | 2,057 B | ~748 B | 0.3636 | ~2,236 B | 1.0870 | **DEFLATE** |
| `05_random_binary.bin` | 2,048 B | ~2,176 B | 1.0625 | ~3,051 B | 1.4902 | — (both expand) |

---

## Usage

```bash
# Generate test files
head -c 1MB /dev/urandom > random_file.txt  

# DEFLATE
python main.py -c <file>      # compress
python main.py -d <file>.sdfl # decompress

# Range Coding 
python main.py -rc <file>      # compress
python main.py -rd <file>.rng  # decompress

# Benchmark mode (measure time & ratio)
python main.py -m True -c  <file>
python main.py -m True -rc <file>
```