"""Bitmap glyphs as lists of 0/1 rows, stored as JSON {char: ["0110...", ...]}.

The workbench operations build a missing Hangul syllable from parts of glyphs
that already exist (a rectangle of rows/columns copied over a base glyph).
"""
import json
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return {k: parse(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}


def save(path, glyphs):
    data = {k: ["".join(map(str, r)) for r in g] for k, g in glyphs.items()}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def parse(rows):
    """Rows as '0101' / '.#.#' strings -> list of int lists."""
    return [[1 if c in "1#" else 0 for c in r] for r in rows]


def art(g):
    return ["".join("#" if p else "." for p in r) for r in g]


def side_by_side(named):
    """[(name, glyph)] -> printable lines, glyphs next to each other."""
    arts = [(n, art(g)) for n, g in named]
    w = [max(len(n), max((len(r) for r in a), default=0)) for n, a in arts]
    lines = ["  ".join(f"{n:<{w[i]}}" for i, (n, _) in enumerate(arts)).rstrip()]
    for y in range(max((len(a) for _, a in arts), default=0)):
        lines.append("  ".join((a[y] if y < len(a) else "").ljust(w[i]) for i, (_, a) in enumerate(arts)).rstrip())
    return lines


def transplant(base, src, rows, cols):
    """Copy the inclusive rectangle rows=(r0, r1), cols=(c0, c1) from `src` onto a copy of `base`."""
    g = [list(r) for r in base]
    for y in range(rows[0], rows[1] + 1):
        for x in range(cols[0], cols[1] + 1):
            g[y][x] = src[y][x]
    return g


def parse_spec(spec):
    """'name=src:r0-r1,c0-c1' (name is a label only) -> (src, (r0, r1), (c0, c1))."""
    src, rc = spec.split("=", 1)[-1].split(":")
    rr, cc = rc.split(",")
    r0, r1 = map(int, rr.split("-"))
    c0, c1 = map(int, cc.split("-"))
    return src, (r0, r1), (c0, c1)
