"""Read bitmap glyphs back as text with macOS Vision (macOS only).

Glyphs are drawn large in rows of N, each row is recognised as one line, and a
row is trusted only when the recognised length equals its glyph count. Vision
is reached through ocr.swift, compiled once with swiftc into a cache directory.
"""
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageFilter

SWIFT = Path(__file__).with_name("ocr.swift")


def _cache():
    base = os.getenv("XDG_CACHE_HOME") or os.path.join(Path.home(), ".cache")
    return Path(base) / "sfc-kr-toolkit"


def binary():
    """Path of the compiled Vision helper, building it when missing or stale."""
    if sys.platform != "darwin":
        raise RuntimeError("OCR needs macOS (Vision framework)")
    exe = _cache() / "sfckr-ocr"
    if not exe.exists() or exe.stat().st_mtime < SWIFT.stat().st_mtime:
        exe.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["xcrun", "swiftc", "-O", str(SWIFT), "-o", str(exe)], check=True)
    return exe


def row_image(glyphs, scale=8, blur=0.0, spacing=3, margin=40):
    """One line of glyphs (lists of 0/1 rows) as a black-on-white image."""
    h = max(len(g) for g in glyphs)
    w = sum(len(g[0]) + spacing for g in glyphs)
    im = Image.new("L", (w * scale + margin * 2, h * scale + margin * 2), 255)
    x0 = margin
    for g in glyphs:
        for y, row in enumerate(g):
            for x, p in enumerate(row):
                if p:
                    im.paste(0, (x0 + x * scale, margin + y * scale, x0 + (x + 1) * scale, margin + (y + 1) * scale))
        x0 += (len(g[0]) + spacing) * scale
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return im


def recognize(paths, lang="ko-KR"):
    """[(text, confidence)] for each image path."""
    env = dict(os.environ, OCR_LANG=lang)
    res = subprocess.run([str(binary())] + [str(p) for p in paths],
                         capture_output=True, text=True, env=env, check=True)
    out = []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        out.append((parts[1] if len(parts) > 1 else "", float(parts[2]) if len(parts) > 2 else 0.0))
    return out


def ocr_glyphs(glyphs, outdir, per_row=10, scale=8, blur=0.0, lang="ko-KR"):
    """{key: char or None} for an ordered {key: glyph} mapping."""
    keys = list(glyphs)
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for i in range(0, len(keys), per_row):
        ks = keys[i:i + per_row]
        p = Path(outdir) / f"{i:05d}.png"
        row_image([glyphs[k] for k in ks], scale, blur).save(p)
        rows.append((p, ks))
    result = {}
    for (text, _), (_, ks) in zip(recognize([p for p, _ in rows], lang), rows):
        text = text.replace(" ", "")
        for n, k in enumerate(ks):
            result[k] = text[n] if len(text) == len(ks) else None
    return result
