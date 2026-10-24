"""Linear (non-tiled) bitmaps: rows of packed pixels, `bpp` bits each.

`order` is the pixel order inside a byte: "lsb" puts the first pixel in the
low bits (NDS 4bpp tiles and most DS fonts), "msb" in the high bits.
"""
from PIL import Image


def glyph_size(w, h, bpp):
    if (w * h * bpp) % 8:
        raise ValueError(f"{w}x{h} at {bpp}bpp is not a whole number of bytes")
    return w * h * bpp // 8


def decode(data, w, h, bpp, order="lsb", off=0):
    """One bitmap as a list of rows of colour indices."""
    if bpp not in (1, 2, 4, 8) or order not in ("lsb", "msb"):
        raise ValueError("bpp is 1, 2, 4 or 8 and order is lsb or msb")
    per = 8 // bpp
    mask = (1 << bpp) - 1
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            i = y * w + x
            b = data[off + i // per]
            k = i % per if order == "lsb" else per - 1 - i % per
            row.append(b >> (k * bpp) & mask)
        rows.append(row)
    return rows


def encode(pix, bpp, order="lsb"):
    h, w = len(pix), len(pix[0])
    out = bytearray(glyph_size(w, h, bpp))
    per = 8 // bpp
    for y in range(h):
        for x in range(w):
            v = pix[y][x]
            if not 0 <= v < 1 << bpp:
                raise ValueError(f"colour {v} does not fit {bpp}bpp")
            i = y * w + x
            k = i % per if order == "lsb" else per - 1 - i % per
            out[i // per] |= v << (k * bpp)
    return bytes(out)


def sheet(data, w, h, bpp, order="lsb", start=0, count=None, cols=16, scale=2):
    """Grey PNG sheet of consecutive bitmaps (index 0 white), one-pixel grid."""
    size = glyph_size(w, h, bpp)
    total = len(data) // size - start
    count = total if count is None else min(count, total)
    if count <= 0:
        raise ValueError("no bitmaps in range")
    rows = -(-count // cols)
    img = Image.new("L", (cols * (w + 1) + 1, rows * (h + 1) + 1), 128)
    top = (1 << bpp) - 1
    for g in range(count):
        pix = decode(data, w, h, bpp, order, (start + g) * size)
        ox, oy = 1 + (g % cols) * (w + 1), 1 + (g // cols) * (h + 1)
        for y in range(h):
            for x in range(w):
                img.putpixel((ox + x, oy + y), 255 - pix[y][x] * 255 // top)
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)
