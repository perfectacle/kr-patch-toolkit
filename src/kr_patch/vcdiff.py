"""VCDIFF (RFC 3284) patches as written by xdelta3.

`apply` is a pure-Python decoder for the default code table, with the xdelta3
extensions it needs: an application header (skipped) and a per-window Adler-32
of the target (checked). Secondary compression and custom code tables are not
supported; `make` writes patches without them (`-S none`).
"""
import shutil
import subprocess
import zlib

MAGIC = b"\xD6\xC3\xC4\x00"
VCD_SOURCE, VCD_TARGET, VCD_ADLER32 = 1, 2, 4
NOOP, ADD, RUN, COPY = 0, 1, 2, 3
NEAR, SAME = 4, 3


def _code_table():
    t = [(RUN, 0, 0, NOOP, 0, 0), (ADD, 0, 0, NOOP, 0, 0)]
    t += [(ADD, s, 0, NOOP, 0, 0) for s in range(1, 18)]
    for m in range(9):
        t.append((COPY, 0, m, NOOP, 0, 0))
        t += [(COPY, s, m, NOOP, 0, 0) for s in range(4, 19)]
    for m in range(6):
        t += [(ADD, a, 0, COPY, c, m) for a in range(1, 5) for c in range(4, 7)]
    for m in range(6, 9):
        t += [(ADD, a, 0, COPY, 4, m) for a in range(1, 5)]
    t += [(COPY, 4, m, ADD, 1, 0) for m in range(9)]
    assert len(t) == 256
    return t


CODE_TABLE = _code_table()


class _Reader:
    def __init__(self, data, pos=0, end=None):
        self.d, self.p, self.end = data, pos, len(data) if end is None else end

    def byte(self):
        if self.p >= self.end:
            raise ValueError("VCDIFF: unexpected end of data")
        b = self.d[self.p]; self.p += 1
        return b

    def varint(self):
        v = 0
        for _ in range(10):
            b = self.byte()
            v = v << 7 | (b & 0x7F)
            if not b & 0x80:
                return v
        raise ValueError("VCDIFF: integer too long")

    def take(self, n):
        if self.p + n > self.end:
            raise ValueError("VCDIFF: section runs past the end")
        b = self.d[self.p:self.p + n]; self.p += n
        return b


def header(patch):
    """{'appheader': bytes or None} of a VCDIFF file. Raises ValueError on
    features `apply` does not support."""
    r = _Reader(patch)
    if r.take(4) != MAGIC:
        raise ValueError("not a VCDIFF file")
    ind = r.byte()
    if ind & 1:
        raise ValueError("VCDIFF secondary compression is not supported (make the patch with -S none)")
    if ind & 2:
        raise ValueError("VCDIFF custom code tables are not supported")
    app = r.take(r.varint()) if ind & 4 else None
    return {"appheader": app, "windows_at": r.p}


def apply(source, patch):
    """Target bytes from `source` and a VCDIFF `patch`. Raises ValueError on a
    malformed patch or an Adler-32 mismatch (wrong source file)."""
    r = _Reader(patch, header(patch)["windows_at"])
    out = bytearray()
    win = 0
    while r.p < len(patch):
        ind = r.byte()
        if ind & ~(VCD_SOURCE | VCD_TARGET | VCD_ADLER32) or ind & VCD_SOURCE and ind & VCD_TARGET:
            raise ValueError(f"VCDIFF window {win}: bad window indicator {ind:#04x}")
        seg = b""
        if ind & (VCD_SOURCE | VCD_TARGET):
            slen, spos = r.varint(), r.varint()
            src = source if ind & VCD_SOURCE else out
            if spos + slen > len(src):
                raise ValueError(f"VCDIFF window {win}: source segment past the end of the {'source' if ind & VCD_SOURCE else 'target'}")
            seg = bytes(src[spos:spos + slen])
        delta_len = r.varint()
        delta_at = r.p
        tlen = r.varint()
        if r.byte():
            raise ValueError("VCDIFF compressed sections are not supported")
        dlen, ilen, alen = r.varint(), r.varint(), r.varint()
        adler = int.from_bytes(r.take(4), "big") if ind & VCD_ADLER32 else None
        if r.p - delta_at + dlen + ilen + alen != delta_len:
            raise ValueError(f"VCDIFF window {win}: delta encoding length does not match its sections")
        data = _Reader(patch, r.p, r.p + dlen)
        inst = _Reader(patch, r.p + dlen, r.p + dlen + ilen)
        addr = _Reader(patch, r.p + dlen + ilen, r.p + dlen + ilen + alen)
        r.p += dlen + ilen + alen
        t = _window(seg, tlen, data, inst, addr)
        if adler is not None and zlib.adler32(t) != adler:
            raise ValueError(f"VCDIFF window {win}: Adler-32 mismatch (is the source file the right one?)")
        out += t
        win += 1
    return bytes(out)


def _window(seg, tlen, data, inst, addr):
    slen = len(seg)
    t = bytearray()
    near, same, nxt = [0] * NEAR, [0] * (SAME * 256), 0
    while inst.p < inst.end:
        code = CODE_TABLE[inst.byte()]
        for typ, size, mode in (code[:3], code[3:]):
            if typ == NOOP:
                continue
            if size == 0:
                size = inst.varint()
            if typ == ADD:
                t += data.take(size)
            elif typ == RUN:
                t += data.take(1) * size
            else:
                here = slen + len(t)
                if mode == 0:
                    a = addr.varint()
                elif mode == 1:
                    a = here - addr.varint()
                elif mode < 2 + NEAR:
                    a = near[mode - 2] + addr.varint()
                else:
                    a = same[(mode - 2 - NEAR) * 256 + addr.byte()]
                near[nxt] = a; nxt = (nxt + 1) % NEAR
                same[a % (SAME * 256)] = a
                if a < 0 or a >= here:
                    raise ValueError("VCDIFF: copy address out of range")
                if a + size <= slen:
                    t += seg[a:a + size]
                    continue
                k = 0
                while k < size and a + k < slen:
                    t.append(seg[a + k]); k += 1
                # from the target: copy in chunks no longer than the distance, so overlaps repeat correctly
                while k < size:
                    p = a + k - slen
                    n = min(size - k, len(t) - p)
                    t += t[p:p + n]; k += n
    if len(t) != tlen:
        raise ValueError(f"VCDIFF: window decoded to {len(t)} bytes, header says {tlen}")
    if data.p != data.end or addr.p != addr.end:
        raise ValueError("VCDIFF: data or address section has bytes left over")
    return t


def make(source_path, target_path, out_path, xdelta3="xdelta3", level=9, window=1 << 28):
    """Write a patch with the xdelta3 command: no secondary compression, no
    application header (file names), a source window of `window` bytes so a
    whole cartridge-sized source is searched. Checked by decoding it with
    `apply`. Returns the patch size."""
    exe = shutil.which(xdelta3)
    if not exe:
        raise ValueError(f"{xdelta3} not found on PATH")
    cmd = [exe, "-e", "-f", f"-{level}", "-S", "none", "-A=", "-B", str(window), "-s", str(source_path),
           str(target_path), str(out_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"xdelta3 failed: {e.stderr.decode(errors='replace').strip()}") from None
    with open(source_path, "rb") as f:
        src = f.read()
    with open(target_path, "rb") as f:
        tgt = f.read()
    with open(out_path, "rb") as f:
        patch = f.read()
    if apply(src, patch) != tgt:
        raise ValueError(f"{out_path}: does not reproduce the target")
    return len(patch)
