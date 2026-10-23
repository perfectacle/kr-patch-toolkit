"""Create or apply IPS patches."""

COPIER = 512        # SNES SMC/SWC copier header in front of some dumps
EOF_OFF = 0x454F46  # "EOF" as an offset would be read as the end marker
MAX_LEN = 0xFFFF
GAP = 6


def make(a, b, header=False, gap=GAP):
    """Patch that turns `a` into `b`.

    A record ends at the first run of `gap` equal bytes; shorter equal runs are
    copied inside the record, since a new record costs 5 bytes of header.
    Different gaps give different (equally valid) patches, so keep the value a
    project has shipped with if its patches must stay byte-identical.

    header=True writes offsets for the same images behind a 512-byte SNES
    copier header, so one build can ship patches for headerless and headered dumps.
    """
    if header:
        a, b = bytes(COPIER) + bytes(a), bytes(COPIER) + bytes(b)
    if len(b) < len(a) or len(b) > 0xFFFFFF:
        raise ValueError("target must be at least as large as the source and below 16 MB "
                         "(IPS offsets and the size trailer are 24-bit)")
    out = bytearray(b"PATCH")
    i, n = 0, len(b)
    while i < n:
        if i < len(a) and a[i] == b[i]:
            i += 1
            continue
        start = i if i != EOF_OFF else i - 1
        end = i
        while end < n and end - start < MAX_LEN:
            if end >= len(a) or a[end] != b[end]:
                end += 1
                continue
            run = end
            while run < n and run - end < gap and run < len(a) and a[run] == b[run]:
                run += 1
            if run - end >= gap or run >= n:
                break
            end = run
        end = min(end, start + MAX_LEN)
        out += start.to_bytes(3, "big") + (end - start).to_bytes(2, "big") + b[start:end]
        i = end
    out += b"EOF"
    if len(b) > len(a):
        out += len(b).to_bytes(3, "big")
    return bytes(out)


def apply(a, p):
    """Apply patch `p` to `a`. Handles RLE records and the truncation extension."""
    if p[:5] != b"PATCH":
        raise ValueError("not an IPS patch")
    r = bytearray(a)
    i = 5
    while p[i:i + 3] != b"EOF":
        if i + 5 > len(p):
            raise ValueError("IPS patch ends without EOF")
        off = int.from_bytes(p[i:i + 3], "big")
        size = int.from_bytes(p[i + 3:i + 5], "big")
        i += 5
        if size == 0:
            rle = int.from_bytes(p[i:i + 2], "big")
            data = p[i + 2:i + 3] * rle
            i += 3
        else:
            data = p[i:i + size]
            i += size
        if off + len(data) > len(r):
            r.extend(b"\0" * (off + len(data) - len(r)))
        r[off:off + len(data)] = data
    if len(p) >= i + 6:
        r = r[:int.from_bytes(p[i + 3:i + 6], "big")]
    return bytes(r)
