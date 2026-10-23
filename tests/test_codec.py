import random

import pytest

from kr_patch import lzss
from kr_patch.snes import tiles


@pytest.mark.parametrize("data", [
    b"",
    b"A",
    b"\x00" * 100,
    b"ABCABCABCABCABCABC" * 10,
    bytes(range(256)) * 3,
    b"\x00\x00\x00hello\x00\x00\x00hello world",
])
def test_round_trip(data):
    enc = lzss.compress(data)
    dec, n = lzss.decompress(enc)
    assert dec == data
    assert n == len(enc)


def test_round_trip_random():
    rnd = random.Random(1234)
    for _ in range(30):
        data = bytes(rnd.choice([0, 1, 2, 0xFF]) for _ in range(rnd.randrange(1, 2000)))
        assert lzss.decompress(lzss.compress(data))[0] == data


def test_decompress_at_offset():
    enc = lzss.compress(b"tile data tile data")
    blob = b"\xEE" * 7 + enc + b"\xEE" * 3
    assert lzss.decompress(blob, 7) == (b"tile data tile data", len(enc))


def test_known_stream():
    # size 6, flags 0b11 (two literals 'a','b'), then copy dist 2 len 4
    w = (2 << 4) | (4 - 3)
    stream = bytes([6, 0, 0b011, ord("a"), ord("b"), w & 0xFF, w >> 8])
    assert lzss.decompress(stream)[0] == b"ababab"


def test_leading_zeros_use_virtual_window():
    data = b"\x00" * 18 + b"x"
    enc = lzss.compress(data)
    assert len(enc) < len(data)
    assert lzss.decompress(enc)[0] == data


def test_compress_rejects_oversize():
    with pytest.raises(ValueError):
        lzss.compress(bytes(0x10000))


def test_planar_conversion():
    tile = bytes(range(16))
    snes = tiles.planar_to_snes(tile)
    assert snes[:4] == bytes([0, 8, 1, 9])
    assert tiles.snes_to_planar(snes) == tile


@pytest.mark.parametrize("stream,match", [
    (b"\x05", "truncated"),
    (bytes([4, 0, 0b1, ord("a")]), "truncated"),            # flag byte promises a copy word
    (bytes([4, 0, 0b0, 0x01, 0x00]), "distance 0"),
])
def test_decompress_rejects_bad_streams(stream, match):
    with pytest.raises(ValueError, match=match):
        lzss.decompress(stream)
