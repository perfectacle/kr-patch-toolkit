"""CPU address <-> ROM file offset for the common SNES cartridge maps.

Offsets are into a headerless image. `to_offset` is deliberately permissive: it
masks the address the way the board decodes it and does not reject addresses
that hit RAM or I/O, so a disassembler can follow mirrors without special cases.
"""


class Mapper:
    name = ""
    header = 0x7FC0     # internal header ($xxFFC0) as a file offset

    def to_offset(self, addr):
        raise NotImplementedError

    def to_cpu(self, off):
        raise NotImplementedError

    def __repr__(self):
        return f"<{type(self).__name__}>"


class LoROM(Mapper):
    """32 KB banks at $8000-$FFFF. `bank_base` $80 gives FastROM addresses."""
    name = "lorom"

    def __init__(self, bank_base=0x80):
        self.bank_base = bank_base

    def to_offset(self, addr):
        bank, lo = addr >> 16, addr & 0xFFFF
        return ((bank & 0x7F) << 15) | (lo & 0x7FFF)

    def to_cpu(self, off):
        return ((self.bank_base | (off >> 15)) << 16) | 0x8000 | (off & 0x7FFF)


class HiROM(Mapper):
    """64 KB banks at $C0-$FF (mirrored at $40-$7D and the upper half of $00-$3F/$80-$BF)."""
    name = "hirom"
    header = 0xFFC0

    def to_offset(self, addr):
        return ((addr >> 16 & 0x3F) << 16) | (addr & 0xFFFF)

    def to_cpu(self, off):
        return 0xC00000 | (off & 0x3FFFFF)


class ExHiROM(Mapper):
    """Up to 8 MB: $C0-$FF hold the first 4 MB, $40-$7D the rest."""
    name = "exhirom"
    header = 0x40FFC0

    def to_offset(self, addr):
        bank = addr >> 16
        base = 0 if bank & 0x80 else 0x400000
        return base | ((bank & 0x3F) << 16) | (addr & 0xFFFF)

    def to_cpu(self, off):
        if off < 0x400000:
            return 0xC00000 | off
        return 0x400000 | (off - 0x400000)


class SA1(Mapper):
    """SA-1 with the default Super MMC banks: $C0-$FF are 64 KB HiROM-style banks,
    $00-$3F/$80-$BF:8000-FFFF mirror the first 2 MB as 32 KB LoROM-style banks."""
    name = "sa1"

    def to_offset(self, addr):
        bank, lo = addr >> 16, addr & 0xFFFF
        if bank >= 0xC0:
            return ((bank & 0x3F) << 16) | lo
        return ((bank & 0x3F) << 15) | (lo & 0x7FFF)

    def to_cpu(self, off):
        return 0xC00000 | (off & 0x3FFFFF)


MAPPERS = {m.name: m for m in (LoROM, HiROM, ExHiROM, SA1)}


def get(name):
    try:
        return MAPPERS[name.lower()]()
    except KeyError:
        raise ValueError(f"unknown mapper {name!r} (one of {', '.join(MAPPERS)})") from None
