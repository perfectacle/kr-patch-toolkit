import random

import pytest

from kr_patch import lz11

SAMPLES = [
    b"",
    b"A",
    b"\x00" * 100,
    b"\x00" * 5000,
    b"ABCABCABCABCABCABC" * 10,
    bytes(range(256)) * 20,
    b"\x00\x00\x00hello\x00\x00\x00hello world",
]


@pytest.mark.parametrize("kind", [0x10, 0x11])
@pytest.mark.parametrize("data", SAMPLES)
def test_round_trip(kind, data):
    enc = lz11.compress(data, kind)
    assert enc[0] == kind
    assert lz11.decompress(enc) == (data, len(enc))


def test_round_trip_random():
    rnd = random.Random(1234)
    for _ in range(20):
        data = bytes(rnd.choice([0, 1, 2, 0xFF]) for _ in range(rnd.randrange(1, 6000)))
        assert lz11.decompress(lz11.compress(data))[0] == data


def test_lz11_uses_long_references():
    # one literal, then a single 4-byte reference covers the rest
    enc = lz11.compress(b"\x00" * 5000)
    assert len(enc) < 16


def test_known_lz11_stream():
    # size 6; flags 0b01000000: literal 'a', then 2-byte ref length 5 distance 1
    stream = bytes([0x11, 6, 0, 0, 0b01000000, ord("a"), (5 - 1) << 4, 0])
    assert lz11.decompress(stream) == (b"aaaaaa", len(stream))


def test_known_lz10_stream():
    stream = bytes([0x10, 6, 0, 0, 0b01000000, ord("a"), (5 - 3) << 4, 0])
    assert lz11.decompress(stream) == (b"aaaaaa", len(stream))


def test_decompress_at_offset():
    enc = lz11.compress(b"tile data tile data")
    assert lz11.decompress(b"\xEE" * 7 + enc + b"\xEE", 7) == (b"tile data tile data", len(enc))


@pytest.mark.parametrize("bad", [b"\x12\x01\x00\x00", b"\x11\x05\x00\x00\x00ab", b"\x11\x04\x00\x00\x80\x30\x05"])
def test_errors(bad):
    with pytest.raises(ValueError):
        lz11.decompress(bad)


def test_same_input_same_output():
    data = bytes(random.Random(7).randrange(4) for _ in range(3000))
    assert lz11.compress(data) == lz11.compress(data)


@pytest.mark.parametrize("kind", [0x10, 0x11])
def test_vram_safe_has_no_distance_one(kind):
    data = b"\0" * 300 + b"ab" * 40
    enc = lz11.compress(data, kind, min_dist=2)
    assert lz11.decompress(enc)[0] == data
    assert enc != lz11.compress(data, kind)


def test_lz10_empty_uses_the_short_header():
    assert lz11.compress(b"", 0x10) == b"\x10\0\0\0"
    assert lz11.decompress(b"\x10\0\0\0") == (b"", 4)
