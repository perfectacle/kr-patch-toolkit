"""Synthetic ROM images: a valid internal header, a reset vector and some code."""
import pytest

from kr_patch.sfc import header, mapper

MODES = {"lorom": 0x20, "hirom": 0x21, "sa1": 0x23, "exhirom": 0x25}


def make_rom(kind="lorom", size=0x80000, title=b"SFCKR TEST", code=b"", code_at=None, fill=0xFF):
    mp = mapper.get(kind)
    rom = bytearray([fill]) * size
    h = mp.header
    rom[h:h + 21] = title.ljust(21, b" ")
    rom[h + 0x15] = MODES[kind]
    rom[h + 0x17] = max(0, (size // 1024).bit_length() - 1)    # ROM size: 1 KB << n
    rom[h + 0x3C:h + 0x3E] = (0x8000).to_bytes(2, "little")   # emulation-mode RESET
    if code:
        at = mp.to_offset(code_at) if code_at is not None else (mp.to_offset(0x008000) if kind == "lorom" else 0)
        rom[at:at + len(code)] = code
    fixed, _ = header.fix(bytes(rom), mp)
    return fixed


@pytest.fixture
def rom_factory():
    return make_rom
