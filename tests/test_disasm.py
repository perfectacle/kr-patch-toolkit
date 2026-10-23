from sfc_kr.disasm import decode, disasm
from sfc_kr.rom import mapper

# REP #$30; LDA #$1234; LDX #$5678; SEP #$20; LDA #$9A; BRA -2; JSL $C08000; MVN $7E,$7F; BRL +0
CODE = bytes.fromhex("C230 A93412 A27856 E220 A99A 80FE 220080C0 547F7E 820000")


def test_lorom_listing(rom_factory):
    rom = rom_factory("lorom", code=CODE, code_at=0x808000)
    out = disasm(rom, 0x808000, 9, mapper=mapper.LoROM()).splitlines()
    assert out == [
        "80:8000  c2 30        REP #$30",
        "80:8002  a9 34 12     LDA #$1234",
        "80:8005  a2 78 56     LDX #$5678",
        "80:8008  e2 20        SEP #$20",
        "80:800A  a9 9a        LDA #$9A",
        "80:800C  80 fe        BRA $80800C",
        "80:800E  22 00 80 c0  JSL $C08000",
        "80:8012  54 7f 7e     MVN $7F,$7E",
        "80:8015  82 00 00     BRL $808018",
    ]


def test_initial_widths():
    rom = bytes.fromhex("A93412A27856") + bytes(0x8000)
    text, n, m8, x8 = decode(rom, 0x008000, m8=False, x8=True)
    assert text.endswith("LDA #$1234") and n == 3 and not m8
    text, n, _, _ = decode(rom, 0x008003, m8=False, x8=True)
    assert text.endswith("LDX #$78") and n == 2


def test_mapper_injection(rom_factory):
    # same bytes at HiROM offset 0 and SA-1 offset 0, addressed through bank $C0
    for kind, mp in (("hirom", mapper.HiROM()), ("sa1", mapper.SA1())):
        rom = rom_factory(kind, code=CODE, code_at=0xC00000)
        first = disasm(rom, 0xC00000, 1, mapper=mp)
        assert first == "C0:0000  c2 30        REP #$30"
    # SA-1 banks $00-$3F read the same ROM as LoROM-style 32 KB banks
    rom = rom_factory("sa1", code=CODE, code_at=0x008000)
    assert disasm(rom, 0x008000, 1, mapper=mapper.SA1()).endswith("REP #$30")


def test_bank_wraps_within_bank():
    rom = bytearray(0x10000)
    rom[0x7FFF] = 0xEA       # NOP at $00:FFFF
    rom[0x0000] = 0x60       # RTS at $00:0000 (LoROM maps it to offset 0)
    out = disasm(bytes(rom), 0x00FFFF, 2).splitlines()
    assert out[0].startswith("00:FFFF") and out[0].endswith("NOP")
    assert out[1].startswith("00:0000") and out[1].endswith("RTS")
