import struct

import pytest

from kr_patch.nds import rom as R


def make_nds(files=None, overlay=b"OVL0" * 8, gap=0x40):
    """Tiny NDS image: header, ARM9/ARM7, one ARM9 overlay (file 0), and
    a.bin (1) in the root, sub/b.bin (2) and sub/c.bin (3). Files are
    `gap` bytes apart, padded with 0xFF."""
    files = files or {"a.bin": b"A" * 0x30, "sub/b.bin": b"B" * 0x20, "sub/c.bin": b"C" * 0x10}
    rom = bytearray(b"\xFF" * 0x8000)
    rom[0:12] = b"KRPATCH TEST"
    rom[12:16] = b"KRPT"
    rom[0x10:0x20] = bytes(16)   # maker, unit code (plain NDS), capacity
    arm9, arm7, fnt, fat, ovt = 0x4000, 0x4100, 0x4200, 0x4300, 0x4400
    rom[arm9:arm9 + 0x100] = b"\x09" * 0x100
    rom[arm7:arm7 + 0x100] = b"\x07" * 0x100

    def name(n):
        return bytes([len(n)]) + n.encode()

    root = name("a.bin") + bytes([0x83]) + b"sub" + struct.pack("<H", 0xF001) + b"\0"
    sub = name("b.bin") + name("c.bin") + b"\0"
    main = struct.pack("<IHH", 16, 1, 2) + struct.pack("<IHH", 16 + len(root), 2, 0xF000)
    table = main + root + sub
    rom[fnt:fnt + len(table)] = table
    blobs = [overlay, files["a.bin"], files["sub/b.bin"], files["sub/c.bin"]]
    pos = 0x5000
    for i, blob in enumerate(blobs):
        rom[pos:pos + len(blob)] = blob
        struct.pack_into("<II", rom, fat + i * 8, pos, pos + len(blob))
        pos += -(-(len(blob) + gap) // 0x10) * 0x10
    struct.pack_into("<8I", rom, ovt, 0, 0x02100000, len(overlay), 0, 0, 0, 0, 0)
    struct.pack_into("<IIII", rom, 0x20, arm9, 0x02000000, 0x02000000, 0x100)
    struct.pack_into("<IIII", rom, 0x30, arm7, 0x02380000, 0x02380000, 0x100)
    struct.pack_into("<IIIIIIII", rom, 0x40, fnt, len(table), fat, 4 * 8, ovt, 32, 0, 0)
    struct.pack_into("<I", rom, 0x68, 0)
    struct.pack_into("<I", rom, 0x80, pos)
    rom[0x14] = 0
    struct.pack_into("<H", rom, 0x15E, R.crc16(rom[:0x15E]))
    return bytes(rom)


def test_crc16_known_value():
    assert R.crc16(b"123456789") == 0x4B37


def test_parse():
    r = R.Rom(make_nds())
    assert (r.title, r.code) == ("KRPATCH TEST", "KRPT")
    assert r.names == {1: "a.bin", 2: "sub/b.bin", 3: "sub/c.bin"}
    assert r.overlay_files() == {"overlay9/overlay_0000.bin": 0}
    assert r.file(r.find("sub/b.bin")) == b"B" * 0x20
    with pytest.raises(ValueError):
        r.find("nope")


def test_unpack_pack_round_trip(tmp_path):
    base = make_nds()
    r = R.Rom(base)
    assert R.unpack(r, tmp_path) == 9
    assert (tmp_path / "data/sub/c.bin").read_bytes() == b"C" * 0x10
    out, changed = R.pack(r, tmp_path)
    assert out == base and changed == []


def test_shrink_and_grow_in_place():
    r = R.Rom(make_nds())
    out = R.Rom(R.rebuild(r, {1: b"a" * 0x10, 2: b"b" * 0x50}))
    assert out.file(1) == b"a" * 0x10 and out.file(2) == b"b" * 0x50
    assert out.entries[1][0] == r.entries[1][0] and out.entries[2][0] == r.entries[2][0]
    # the freed tail of a.bin is padding, not stale data
    s = r.entries[1][0]
    assert out.data[s + 0x10:s + 0x30] == b"\xFF" * 0x20
    assert R.crc16(out.data[:0x15E]) == struct.unpack_from("<H", out.data, 0x15E)[0]


def test_too_big_moves_to_end_aligned():
    r = R.Rom(make_nds())
    out = R.Rom(R.rebuild(r, {2: b"x" * 0x1000}))
    s, e = out.entries[2]
    assert s % R.ALIGN == 0 and s >= r.used and out.file(2) == b"x" * 0x1000
    assert out.used == e and out.file(3) == r.file(3) and out.file(1) == r.file(1)


def test_last_file_grows_without_overlapping_a_moved_file():
    r = R.Rom(make_nds())
    out = R.Rom(R.rebuild(r, {2: b"x" * 0x1000, 3: b"y" * 0x2000}))
    spans = sorted(out.entries[1:])
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    assert out.file(2) == b"x" * 0x1000 and out.file(3) == b"y" * 0x2000


def test_device_capacity_grows():
    r = R.Rom(make_nds())
    out = R.rebuild(r, {3: b"z" * 0x30000})
    assert (0x20000 << out[0x14]) >= len(out)


def test_rebuild_is_deterministic():
    r = R.Rom(make_nds())
    files = {1: b"q" * 0x500, 3: b"w" * 7}
    assert R.rebuild(r, files) == R.rebuild(r, dict(reversed(files.items())))


def test_bad_file_id():
    with pytest.raises(ValueError):
        R.rebuild(R.Rom(make_nds()), {9: b""})


def test_stale_used_size_is_kept_when_nothing_grows():
    rom = bytearray(make_nds())
    struct.pack_into("<I", rom, 0x80, 0x5000)
    struct.pack_into("<H", rom, 0x15E, R.crc16(rom[:0x15E]))
    r = R.Rom(rom)
    assert R.rebuild(r, {}) == bytes(rom)
    assert R.Rom(R.rebuild(r, {1: b"s"})).used == 0x5000


def test_shared_bytes_are_not_overwritten():
    rom = bytearray(make_nds())
    s, e = struct.unpack_from("<II", rom, 0x4300 + 2 * 8)
    struct.pack_into("<II", rom, 0x4300 + 3 * 8, s, e)   # c.bin points at b.bin's bytes
    r = R.Rom(rom)
    out = R.Rom(R.rebuild(r, {2: b"Z" * 0x20}))
    assert out.file(2) == b"Z" * 0x20 and out.file(3) == b"B" * 0x20


def test_signature_after_last_file_is_kept():
    rom = bytearray(make_nds())
    used = struct.unpack_from("<I", rom, 0x80)[0]
    rom[used:used + 0x88] = b"ac" + b"S" * 0x86
    r = R.Rom(rom)
    out = R.Rom(R.rebuild(r, {3: b"G" * 0x400, 2: b"M" * 0x300}))
    assert out.data[used:used + 0x88] == bytes(rom[used:used + 0x88])
    assert out.file(3) == b"G" * 0x400 and out.file(2) == b"M" * 0x300


def test_overlay_must_keep_its_size():
    r = R.Rom(make_nds())
    assert R.Rom(R.rebuild(r, {0: b"X" * 32})).file(0) == b"X" * 32
    with pytest.raises(ValueError, match="overlay"):
        R.rebuild(r, {0: b"X" * 0x80})


def test_dsi_enhanced_is_refused():
    rom = bytearray(make_nds())
    rom[0x12] = 2
    with pytest.raises(ValueError, match="DSi"):
        R.rebuild(R.Rom(rom), {})


def test_fnt_name_cannot_leave_the_folder():
    rom = bytearray(make_nds())
    at = rom.index(b"a.bin")
    rom[at - 1:at + 5] = bytes([2]) + b".." + b"\x03" + b"xyz"
    with pytest.raises(ValueError, match="plain file name"):
        R.Rom(rom)


def test_truncated_rom_is_a_value_error():
    with pytest.raises(ValueError, match="malformed"):
        R.Rom(make_nds()[:0x4210])
