"""Byte ranges where two images differ."""


def ranges(a, b, gap=16):
    """[(start, end_inclusive)] of differing bytes, merging runs closer than `gap`."""
    n = min(len(a), len(b))
    d = [i for i in range(n) if a[i] != b[i]]
    d += range(n, max(len(a), len(b)))
    if not d:
        return []
    out = []
    s = p = d[0]
    for i in d[1:]:
        if i > p + gap:
            out.append((s, p))
            s = i
        p = i
    out.append((s, p))
    return out
