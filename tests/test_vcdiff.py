import random
import shutil
import subprocess
import zlib

import pytest

from kr_patch import vcdiff


def varint(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def window(target, source_len, data, inst, addr, adler=True, comp=0):
    ind = (1 if source_len else 0) | (4 if adler else 0)
    head = bytes([ind]) + (varint(source_len) + varint(0) if source_len else b"")
    body = varint(len(target)) + bytes([comp]) + varint(len(data)) + varint(len(inst)) + varint(len(addr))
    body += zlib.adler32(target).to_bytes(4, "big") if adler else b""
    body += data + inst + addr
    return head + varint(len(body)) + body


def test_varint_matches_rfc_example():
    assert varint(123456789) == bytes([0xBA, 0xEF, 0x9A, 0x15])


def test_hand_built_patch():
    source = b"0123456789abcdef"
    target = b"0123456789XYZ" + b"!" * 5 + b"cdef"
    # COPY 10 from source addr 0 (mode SELF), ADD 3 "XYZ", RUN 5 "!", COPY 4 from source addr 12
    inst = bytes([19, 10, 1, 3, 0, 5, 19, 4])
    addr = varint(0) + varint(12)
    data = b"XYZ" + b"!"
    patch = vcdiff.MAGIC + b"\0" + window(target, len(source), data, inst, addr)
    assert vcdiff.apply(source, patch) == target


def test_copy_from_target_overlaps():
    # no source: ADD "ab", then COPY 6 from target address 0 repeats it
    target = b"ab" * 4
    patch = vcdiff.MAGIC + b"\0" + window(target, 0, b"ab", bytes([3, 19, 6]), varint(0))
    assert vcdiff.apply(b"", patch) == target


def test_app_header_is_skipped():
    target = b"hello"
    patch = vcdiff.MAGIC + b"\x04" + varint(3) + b"x/y" + window(target, 0, target, bytes([1, 5]), b"")
    assert vcdiff.header(patch)["appheader"] == b"x/y"
    assert vcdiff.apply(b"", patch) == target


def test_wrong_source_fails_the_checksum():
    source, target = b"abcdefgh", b"abcdefgh!"
    patch = vcdiff.MAGIC + b"\0" + window(target, len(source), b"!", bytes([19, 8, 2]), varint(0))
    assert vcdiff.apply(source, patch) == target
    with pytest.raises(ValueError, match="Adler-32"):
        vcdiff.apply(b"ABCDEFGH", patch)


@pytest.mark.parametrize("ind", [1, 2])
def test_unsupported_header_features(ind):
    with pytest.raises(ValueError):
        vcdiff.apply(b"", vcdiff.MAGIC + bytes([ind, 0]))


def test_not_vcdiff():
    with pytest.raises(ValueError):
        vcdiff.apply(b"", b"PATCH")


@pytest.mark.skipif(not shutil.which("xdelta3"), reason="xdelta3 not installed")
def test_make_with_xdelta3(tmp_path):
    rnd = random.Random(5)
    src = bytes(rnd.randrange(256) for _ in range(200_000))
    tgt = bytearray(src)
    for _ in range(50):
        p = rnd.randrange(len(tgt) - 100)
        tgt[p:p + rnd.randrange(1, 100)] = bytes(rnd.randrange(256) for _ in range(rnd.randrange(1, 100)))
    (tmp_path / "a").write_bytes(src)
    (tmp_path / "b").write_bytes(bytes(tgt))
    n = vcdiff.make(tmp_path / "a", tmp_path / "b", tmp_path / "p.xdelta")
    patch = (tmp_path / "p.xdelta").read_bytes()
    assert n == len(patch) and vcdiff.header(patch)["appheader"] is None
    assert vcdiff.apply(src, patch) == bytes(tgt)


def test_bad_window_indicator():
    target = b"x"
    for ind in (3, 8):
        w = bytearray(window(target, 0, target, bytes([2]), b""))
        w[0] = ind
        with pytest.raises(ValueError, match="indicator"):
            vcdiff.apply(b"", vcdiff.MAGIC + b"\0" + bytes(w))


def test_leftover_section_bytes():
    target = b"x"
    patch = vcdiff.MAGIC + b"\0" + window(target, 0, b"xy", bytes([2]), b"")
    with pytest.raises(ValueError, match="left over"):
        vcdiff.apply(b"", patch)


def test_long_copy_from_target_in_chunks():
    target = b"abc" * 1000
    patch = vcdiff.MAGIC + b"\0" + window(target, 0, b"abc", bytes([4, 19]) + varint(2997), varint(0))
    assert vcdiff.apply(b"", patch) == target


def lzma_section(raw):
    import lzma
    return varint(len(raw)) + lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_NONE)


def test_lzma_secondary_hand_built():
    # data and inst sections LZMA-compressed, addr section left raw (delta indicator 1|2)
    source = b"0123456789abcdef"
    target = b"0123456789XYZ" + b"!" * 5 + b"cdef"
    data, inst, addr = lzma_section(b"XYZ!"), lzma_section(bytes([19, 10, 1, 3, 0, 5, 19, 4])), varint(0) + varint(12)
    patch = vcdiff.MAGIC + b"\x05\x02" + varint(1) + b"x" + window(target, len(source), data, inst, addr, comp=3)
    assert vcdiff.header(patch)["secondary"] == "lzma"
    assert vcdiff.apply(source, patch) == target


def test_compressed_section_without_secondary_header():
    target = b"x"
    w = window(target, 0, lzma_section(target), bytes([2]), b"", comp=1)
    with pytest.raises(ValueError, match="no secondary compressor"):
        vcdiff.apply(b"", vcdiff.MAGIC + b"\0" + w)


@pytest.mark.parametrize("sid,name", [(1, "djw"), (16, "fgk"), (9, "id 9")])
def test_other_secondary_compressors_are_named(sid, name):
    with pytest.raises(ValueError, match=f"compressor {name} is not supported"):
        vcdiff.header(vcdiff.MAGIC + bytes([1, sid]))


@pytest.mark.skipif(not shutil.which("xdelta3"), reason="xdelta3 not installed")
def test_apply_xdelta3_lzma_patch(tmp_path):
    # small windows (-W) so the LZMA streams carry on across many windows; the
    # default application header (file names) is kept
    rnd = random.Random(7)
    words = [bytes(rnd.randrange(256) for _ in range(rnd.randrange(3, 12))) for _ in range(64)]
    src = b"".join(rnd.choice(words) for _ in range(40_000))
    tgt = bytearray(src)
    for _ in range(300):
        p = rnd.randrange(len(tgt) - 64)
        tgt[p:p + rnd.randrange(1, 64)] = b"".join(rnd.choice(words) for _ in range(rnd.randrange(1, 8)))
    (tmp_path / "a").write_bytes(src)
    (tmp_path / "b").write_bytes(bytes(tgt))
    subprocess.run(["xdelta3", "-e", "-f", "-9", "-S", "lzma", "-W", "16384", "-s", str(tmp_path / "a"),
                    str(tmp_path / "b"), str(tmp_path / "p.xdelta")], check=True, capture_output=True)
    patch = (tmp_path / "p.xdelta").read_bytes()
    h = vcdiff.header(patch)
    assert h["secondary"] == "lzma" and h["appheader"]
    assert vcdiff.apply(src, patch) == bytes(tgt)
    with pytest.raises(ValueError, match="Adler-32"):
        vcdiff.apply(src[:100] + b"\xFF" + src[101:], patch)
