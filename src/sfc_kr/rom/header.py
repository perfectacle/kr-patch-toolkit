"""Internal header, checksum and copier header handling."""
from . import mapper as M

COPIER = 512            # SMC/SWC copier header in front of some dumps

# map mode byte ($FFD5) low nibble / exact values
_MODES = {0x20: "lorom", 0x30: "lorom", 0x21: "hirom", 0x31: "hirom",
          0x23: "sa1", 0x25: "exhirom", 0x35: "exhirom"}


def has_copier(data):
    return len(data) % 0x400 == COPIER


def strip_copier(data):
    return data[COPIER:] if has_copier(data) else data


def _mirror_sum(d, size):
    # sum of `d` mirrored up to `size` (a power of two >= len(d))
    n = len(d)
    big = 1 << (n.bit_length() - 1)
    if big == n:
        return sum(d) * (size // n)
    return (sum(d[:big]) + _mirror_sum(d[big:], big)) * (size // (2 * big))


def checksum(rom):
    """SNES checksum of a headerless image.

    Sizes that are not a power of two are summed as the cartridge mirrors them:
    the largest power-of-two part, then the remainder repeated up to that size.
    """
    rom = bytes(rom)
    if not rom:
        return 0
    return _mirror_sum(rom, 1 << (len(rom) - 1).bit_length()) & 0xFFFF


def _need(rom, mp):
    if len(rom) < mp.header + 0x40:
        raise ValueError(f"{len(rom):#x}-byte image has no {mp.name} header at {mp.header:#x}")


def _blank(rom, hdr):
    r = bytearray(rom)
    r[hdr + 0x1C:hdr + 0x20] = b"\xff\xff\x00\x00"   # complement/checksum bytes always sum to 0x1FE
    return r


def compute(rom, mp):
    """Checksum the image would have with its complement/checksum fields filled in."""
    _need(rom, mp)
    return checksum(_blank(rom, mp.header))


def fix(rom, mp):
    """Return a copy of `rom` (headerless) with the header checksum fields rewritten."""
    _need(rom, mp)
    r = _blank(rom, mp.header)
    s = checksum(r)
    h = mp.header
    r[h + 0x1C:h + 0x20] = bytes([~s & 0xFF, (~s >> 8) & 0xFF, s & 0xFF, s >> 8])
    return bytes(r), s


def stored(rom, mp):
    """(complement, checksum) as stored in the header."""
    _need(rom, mp)
    h = mp.header
    return (rom[h + 0x1C] | rom[h + 0x1D] << 8, rom[h + 0x1E] | rom[h + 0x1F] << 8)


def title(rom, mp):
    _need(rom, mp)
    return bytes(rom[mp.header:mp.header + 21]).decode("ascii", "replace").rstrip()


def map_mode(rom, mp):
    _need(rom, mp)
    return rom[mp.header + 0x15]


def _score(rom, mp):
    h = mp.header
    if len(rom) < h + 0x40:
        return -1
    s = 0
    comp, csum = stored(rom, mp)
    if comp ^ csum == 0xFFFF:
        s += 4
    mode = rom[h + 0x15]
    if _MODES.get(mode) == mp.name:
        s += 4
    elif mode & 0xE0 == 0x20:
        s += 1
    reset = rom[h + 0x3C] | rom[h + 0x3D] << 8
    if reset >= 0x8000:
        s += 2
    if all(0x20 <= c < 0x7F or c >= 0xA0 for c in rom[h:h + 21]):
        s += 1
    return s


CONFIDENT = 5   # a matching map mode plus one more sign


def detect_score(rom):
    """(mapper, score) for the best-looking internal header. Scores below
    CONFIDENT mean the header is probably not where that mapper puts it."""
    best, best_score = M.LoROM(), -1
    for cls in (M.LoROM, M.SA1, M.HiROM, M.ExHiROM):
        mp = cls()
        sc = _score(rom, mp)
        if sc > best_score:
            best, best_score = mp, sc
    return best, best_score


def detect(rom):
    """Guess the mapper of a headerless image from its internal header."""
    return detect_score(rom)[0]
