"""iNES and NES 2.0 headers: PRG/CHR sizes, mapper, mirroring, battery, trainer."""
from dataclasses import dataclass

MAGIC = b"NES\x1a"
SIZE = 16
TRAINER = 512


@dataclass
class Header:
    prg_size: int       # bytes
    chr_size: int       # bytes; 0 means the board has CHR-RAM
    mapper: int
    submapper: int
    mirroring: str      # "horizontal", "vertical" or "four-screen"
    battery: bool
    trainer: bool
    nes2: bool

    @property
    def prg_offset(self):
        return SIZE + (TRAINER if self.trainer else 0)


def _nes2_size(lsb, msb, unit):
    if msb == 0xF:      # exponent-multiplier form
        return (1 << (lsb >> 2)) * ((lsb & 3) * 2 + 1)
    return ((msb << 8) | lsb) * unit


def parse(data):
    if len(data) < SIZE or data[:4] != MAGIC:
        raise ValueError("not an iNES image (no 'NES\\x1a' magic)")
    f6, f7 = data[6], data[7]
    nes2 = f7 & 0x0C == 0x08
    mapper = f6 >> 4
    submapper = 0
    if nes2:
        mapper |= (f7 & 0xF0) | (data[8] & 0x0F) << 8
        submapper = data[8] >> 4
        prg = _nes2_size(data[4], data[9] & 0x0F, 0x4000)
        chr_ = _nes2_size(data[5], data[9] >> 4, 0x2000)
    else:
        # Old dumping tools wrote text into bytes 12-15; their byte 7 is not a mapper nibble.
        if not any(data[12:16]):
            mapper |= f7 & 0xF0
        prg, chr_ = data[4] * 0x4000, data[5] * 0x2000
    mirroring = "four-screen" if f6 & 8 else ("vertical" if f6 & 1 else "horizontal")
    return Header(prg, chr_, mapper, submapper, mirroring, bool(f6 & 2), bool(f6 & 4), nes2)


def prg(data):
    """PRG ROM bytes of an iNES image."""
    h = parse(data)
    return bytes(data[h.prg_offset:h.prg_offset + h.prg_size])


def chr_rom(data):
    """CHR ROM bytes (empty for CHR-RAM boards)."""
    h = parse(data)
    o = h.prg_offset + h.prg_size
    return bytes(data[o:o + h.chr_size])
