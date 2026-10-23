import pytest

from sfc_kr.rom import diff, header, ips, mapper


@pytest.mark.parametrize("kind", ["lorom", "hirom", "sa1", "exhirom"])
def test_detect_and_checksum(rom_factory, kind):
    size = 0x500000 if kind == "exhirom" else 0x80000
    rom = rom_factory(kind, size=size)
    mp = header.detect(rom)
    assert mp.name == kind
    comp, csum = header.stored(rom, mp)
    assert comp ^ csum == 0xFFFF
    assert csum == header.compute(rom, mp)
    assert header.title(rom, mp) == "SFCKR TEST"


def test_fix_matches_plain_sum_for_power_of_two(rom_factory):
    rom = bytearray(rom_factory("lorom"))
    rom[0x1234] ^= 0x5A
    fixed, s = header.fix(bytes(rom), mapper.LoROM())
    blank = bytearray(rom)
    blank[0x7FDC:0x7FE0] = b"\xff\xff\x00\x00"
    assert s == sum(blank) & 0xFFFF
    assert fixed[0x7FDE] | fixed[0x7FDF] << 8 == s
    assert fixed[0x7FDC] | fixed[0x7FDD] << 8 == s ^ 0xFFFF


def test_checksum_mirrors_odd_sizes():
    # 3 MB = 2 MB + 1 MB mirrored once
    rom = bytes([1]) * 0x200000 + bytes([2]) * 0x100000
    assert header.checksum(rom) == (0x200000 + 2 * 0x100000 * 2) & 0xFFFF
    # 1.5 MB = 1 MB + (256 KB + 256 KB mirrored to 512 KB) mirrored to 1 MB
    rom = bytes([1]) * 0x100000 + bytes([3]) * 0x40000 + bytes([5]) * 0x40000
    want = 0x100000 + (3 * 0x40000 + 5 * 0x40000) * 2
    assert header.checksum(rom) == want & 0xFFFF


def test_copier_header():
    assert header.has_copier(bytes(0x80200))
    assert not header.has_copier(bytes(0x80000))
    assert header.strip_copier(b"\x01" * 512 + b"\x02" * 1024) == b"\x02" * 1024


@pytest.mark.parametrize("cls,cases", [
    (mapper.LoROM, [(0x808000, 0), (0x80FFFF, 0x7FFF), (0x818000, 0x8000), (0x008000, 0), (0xC37948, 0x21F948)]),
    (mapper.HiROM, [(0xC00000, 0), (0xC12345, 0x12345), (0x408000, 0x8000), (0x01C000, 0x1C000)]),
    (mapper.SA1, [(0xC00000, 0), (0xC12345, 0x12345), (0x008000, 0), (0x018000, 0x8000), (0x3F8000, 0x1F8000)]),
    (mapper.ExHiROM, [(0xC00000, 0), (0xFFFFFF, 0x3FFFFF), (0x400000, 0x400000), (0x7D1234, 0x7D1234),
                      (0x808000, 0x8000)]),
])
def test_mapper_to_offset(cls, cases):
    mp = cls()
    for addr, off in cases:
        assert mp.to_offset(addr) == off, hex(addr)


@pytest.mark.parametrize("name", ["lorom", "hirom", "sa1", "exhirom"])
def test_mapper_round_trip(name):
    mp = mapper.get(name)
    limit = 0x600000 if name == "exhirom" else 0x200000
    for off in range(0, limit, 0x1357):
        assert mp.to_offset(mp.to_cpu(off)) == off


def test_mapper_get_unknown():
    with pytest.raises(ValueError):
        mapper.get("mmc5")


def _mutate(a, spots):
    b = bytearray(a)
    for o, data in spots:
        b[o:o + len(data)] = data
    return bytes(b)


def test_ips_round_trip(rom_factory):
    a = rom_factory("lorom")
    b = _mutate(a, [(0x10, b"\x01\x02\x03"), (0x20, b"\x00" * 300), (0x7FFF0, b"\xAA" * 16)])
    for gap in (6, 7):
        p = ips.make(a, b, gap=gap)
        assert p.startswith(b"PATCH") and p.endswith(b"EOF")
        assert ips.apply(a, p) == b


def _records(p):
    i, out = 5, []
    while p[i:i + 3] != b"EOF":
        off, n = int.from_bytes(p[i:i + 3], "big"), int.from_bytes(p[i + 3:i + 5], "big")
        out.append((off, n))
        i += 5 + n
    return out


def test_ips_gap():
    a = bytes(64)
    b = _mutate(a, [(0, b"\x01"), (7, b"\x01")])   # 6 equal bytes in between
    rec6, rec7 = ips.make(a, b, gap=6), ips.make(a, b, gap=7)
    assert _records(rec6) == [(0, 1), (7, 1)]
    assert _records(rec7) == [(0, 8)]
    assert ips.apply(a, rec6) == ips.apply(a, rec7) == b


def test_ips_headered(rom_factory):
    a = rom_factory("hirom", size=0x40000)
    b = _mutate(a, [(0x100, b"\x42" * 10)])
    p = ips.make(a, b, header=True)
    pad = bytes(512)
    assert ips.apply(pad + a, p) == pad + b
    assert int.from_bytes(p[5:8], "big") == 0x100 + 512


def test_ips_eof_offset():
    a = bytes(0x454F50)
    b = _mutate(a, [(0x454F46, b"\x01")])
    p = ips.make(a, b)
    assert int.from_bytes(p[5:8], "big") == 0x454F45     # starts one byte early
    assert ips.apply(a, p) == b


def test_ips_growth_and_long_records():
    a = bytes(0x100)
    b = a + b"\x11" * 0x20000
    p = ips.make(a, b)
    assert ips.apply(a, p) == b


def test_ips_apply_rle_and_truncate():
    p = b"PATCH" + (4).to_bytes(3, "big") + b"\x00\x00" + (5).to_bytes(2, "big") + b"\x7F" + b"EOF" + (8).to_bytes(3, "big")
    assert ips.apply(bytes(16), p) == b"\x00" * 4 + b"\x7F" * 4


def test_ips_rejects_bad_input():
    with pytest.raises(ValueError):
        ips.apply(b"", b"NOTIPS")
    with pytest.raises(ValueError):
        ips.make(bytes(10), bytes(5))


def test_diff_ranges():
    a = bytes(100)
    b = _mutate(a, [(3, b"\x01"), (10, b"\x01"), (50, b"\x01\x01")])
    assert diff.ranges(a, b, gap=16) == [(3, 10), (50, 51)]
    assert diff.ranges(a, b, gap=2) == [(3, 3), (10, 10), (50, 51)]
    assert diff.ranges(a, a) == []
    assert diff.ranges(a, a + b"\x00\x00") == [(100, 101)]
