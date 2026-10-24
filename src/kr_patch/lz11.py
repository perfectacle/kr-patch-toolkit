"""Nintendo LZ10 / LZ11 (GBA/DS BIOS) codec.

Header: type byte (0x10 or 0x11), u24 LE output size; in LZ11 a size of 0 is
followed by a u32 LE size. Then groups of 8 items led by a flag byte (MSB first).
Flag 0: literal byte. Flag 1: back-reference, distance 1..4096.

LZ10 reference: 2 bytes, length (b0 >> 4) + 3, distance ((b0 & 0xF) << 8 | b1) + 1.
LZ11 reference by the top nibble of b0:
  0: 3 bytes, length ((b0 & 0xF) << 4 | b1 >> 4) + 0x11
  1: 4 bytes, length ((b0 & 0xF) << 12 | b1 << 4 | b2 >> 4) + 0x111
  2-F: 2 bytes, length (b0 >> 4) + 1
and the distance in the low 12 bits of the last two bytes, plus 1.
"""

MAX_DIST = 0x1000
MAX_LEN = {0x10: 0x12, 0x11: 0x10110}
MIN_LEN = 3


def decompress(data, off=0):
    """(data, compressed length) of the stream at `off`. Raises ValueError on an
    unknown type, a stream that ends early or a reference before the start."""
    i = off
    try:
        kind = data[off]
        if kind not in MAX_LEN:
            raise ValueError(f"not an LZ10/LZ11 stream at {off:#x} (type {kind:#04x})")
        size = data[off + 1] | data[off + 2] << 8 | data[off + 3] << 16
        i = off + 4
        if size == 0 and kind == 0x11:
            size = int.from_bytes(data[i:i + 4], "little"); i += 4
        out = bytearray()
        while len(out) < size:
            flags = data[i]; i += 1
            for bit in range(8):
                if len(out) >= size:
                    break
                if not flags & (0x80 >> bit):
                    out.append(data[i]); i += 1
                    continue
                b0 = data[i]
                if kind == 0x10:
                    n = (b0 >> 4) + 3
                    dist = ((b0 & 0xF) << 8 | data[i + 1]) + 1; i += 2
                elif b0 >> 4 == 0:
                    b1, b2 = data[i + 1], data[i + 2]
                    n = ((b0 & 0xF) << 4 | b1 >> 4) + 0x11
                    dist = ((b1 & 0xF) << 8 | b2) + 1; i += 3
                elif b0 >> 4 == 1:
                    b1, b2, b3 = data[i + 1], data[i + 2], data[i + 3]
                    n = ((b0 & 0xF) << 12 | b1 << 4 | b2 >> 4) + 0x111
                    dist = ((b2 & 0xF) << 8 | b3) + 1; i += 4
                else:
                    n = (b0 >> 4) + 1
                    dist = ((b0 & 0xF) << 8 | data[i + 1]) + 1; i += 2
                src = len(out) - dist
                if src < 0:
                    raise ValueError(f"LZ{kind:02X} reference before the start at offset {i:#x}")
                for k in range(n):
                    out.append(out[src + k])
    except IndexError:
        raise ValueError(f"LZ stream at {off:#x} is truncated at offset {i:#x}") from None
    return bytes(out[:size]), i - off


def _longest(data, pos, chains, max_len, min_dist):
    best_len = best_dist = 0
    end = min(len(data), pos + max_len)
    for cand in reversed(chains.get(data[pos:pos + MIN_LEN], ())):
        dist = pos - cand
        if dist > MAX_DIST:
            break
        if dist < min_dist:
            continue
        n = MIN_LEN
        while pos + n < end and data[cand + n] == data[pos + n]:
            n += 1
        if n > best_len:
            best_len, best_dist = n, dist
            if n == end - pos:
                break
    return best_len, best_dist


def compress(data, kind=0x11, min_dist=1):
    """Greedy compression: the longest match within 4096 bytes, the nearest of
    equal length. Same input, same output. `min_dist=2` avoids distance-1
    references, which the BIOS routines that decompress straight to VRAM
    (16-bit writes) get wrong."""
    if kind not in MAX_LEN:
        raise ValueError("kind is 0x10 or 0x11")
    n = len(data)
    if kind == 0x10 and n >= 1 << 24:
        raise ValueError("LZ10 holds less than 16 MiB")
    out = bytearray([kind])
    out += n.to_bytes(3, "little") if kind == 0x10 or 0 < n < 1 << 24 else bytes(3) + n.to_bytes(4, "little")
    chains = {}
    pos = 0
    while pos < n:
        flag_at = len(out)
        out.append(0)
        for bit in range(8):
            if pos >= n:
                break
            length, dist = _longest(data, pos, chains, MAX_LEN[kind], min_dist) if pos + MIN_LEN <= n else (0, 0)
            if length >= MIN_LEN:
                out[flag_at] |= 0x80 >> bit
                d = dist - 1
                if kind == 0x10:
                    out += bytes([(length - 3) << 4 | d >> 8, d & 0xFF])
                elif length <= 0x10:
                    out += bytes([(length - 1) << 4 | d >> 8, d & 0xFF])
                elif length <= 0x110:
                    m = length - 0x11
                    out += bytes([m >> 4, (m & 0xF) << 4 | d >> 8, d & 0xFF])
                else:
                    m = length - 0x111
                    out += bytes([0x10 | m >> 12, (m >> 4) & 0xFF, (m & 0xF) << 4 | d >> 8, d & 0xFF])
            else:
                length = 1
                out.append(data[pos])
            for p in range(pos, pos + length):
                if p + MIN_LEN <= n:
                    chains.setdefault(data[p:p + MIN_LEN], []).append(p)
            pos += length
    return bytes(out)
