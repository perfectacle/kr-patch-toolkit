"""LZSS with a 12-bit distance and 4-bit length word.

Stream: u16 LE output size, then groups of 8 items led by a flag byte (LSB first).
Flag 1: literal byte. Flag 0: u16 LE word, length = (word & 0xF) + 3,
source position = out_pos - (word >> 4); positions before 0 read as zero.

Some games store 2bpp tiles as planar halves (plane 0 rows 0-7, then plane 1
rows 0-7) before compressing; planar_to_snes/snes_to_planar convert that.
"""

MIN_LEN = 3
MAX_LEN = 18
MAX_DIST = 0xFFF


def decompress(rom, off=0):
    """(data, compressed length) of the stream at `off`."""
    size = rom[off] | rom[off + 1] << 8
    i = off + 2
    out = bytearray()
    flags = bits = 0
    while len(out) < size:
        if bits == 0:
            flags = rom[i]; i += 1; bits = 8
        bits -= 1
        bit = flags & 1; flags >>= 1
        if bit:
            out.append(rom[i]); i += 1
        else:
            w = rom[i] | rom[i + 1] << 8; i += 2
            n = (w & 0xF) + MIN_LEN
            src = len(out) - (w >> 4)
            for _ in range(n):
                out.append(out[src] if src >= 0 else 0)
                src += 1
    return bytes(out[:size]), i - off


def compress(data):
    """Greedy LZSS with a brute-force search (inputs are small)."""
    if len(data) > 0xFFFF:
        raise ValueError("LZSS stream holds at most 65535 bytes")
    out = bytearray([len(data) & 0xFF, len(data) >> 8])
    pos = 0
    n = len(data)
    while pos < n:
        flag_at = len(out); out.append(0)
        flags = 0
        for bit in range(8):
            if pos >= n:
                break
            best_len, best_dist = 0, 0
            maxlen = min(MAX_LEN, n - pos)
            for dist in range(1, min(pos, MAX_DIST) + 1):
                s = pos - dist
                l = 0
                while l < maxlen and data[s + l] == data[pos + l]:
                    l += 1
                if l > best_len:
                    best_len, best_dist = l, dist
                    if l == maxlen:
                        break
            # A copy from position -1 reads the virtual zeros before the buffer, then data[0..].
            if best_len < maxlen and pos < MAX_DIST:
                dist = pos + 1
                src = pos - dist
                lz = 0
                while lz < maxlen:
                    v = data[src + lz] if src + lz >= 0 else 0
                    if v != data[pos + lz]:
                        break
                    lz += 1
                if dist <= MAX_DIST and lz > best_len:
                    best_len, best_dist = lz, dist
            if best_len >= MIN_LEN:
                w = (best_dist << 4) | (best_len - MIN_LEN)
                out += bytes([w & 0xFF, w >> 8])
                pos += best_len
            else:
                flags |= 1 << bit
                out.append(data[pos])
                pos += 1
        out[flag_at] = flags
    return bytes(out)


def planar_to_snes(data):
    out = bytearray(len(data))
    for t in range(0, len(data), 16):
        for r in range(8):
            out[t + r * 2] = data[t + r]
            out[t + r * 2 + 1] = data[t + 8 + r]
    return bytes(out)


def snes_to_planar(data):
    out = bytearray(len(data))
    for t in range(0, len(data), 16):
        for r in range(8):
            out[t + r] = data[t + r * 2]
            out[t + 8 + r] = data[t + r * 2 + 1]
    return bytes(out)
