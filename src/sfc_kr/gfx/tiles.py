"""SNES planar tiles: decode to pixel indices and lay them out as an image.

1bpp tiles are one byte per row. 2/4/8bpp tiles store bitplanes in pairs: each
pair is `rows` words (low plane, high plane per row), pairs follow each other.
A tile taller than 8 rows (e.g. a 2bpp 8x12 font glyph) uses the same layout.
"""
from PIL import Image


def tile_size(bpp, rows=8):
    return rows * bpp


def decode(data, off, bpp, rows=8):
    """rows x 8 list of colour indices."""
    out = []
    for y in range(rows):
        r = []
        for x in range(8):
            b = 7 - x
            if bpp == 1:
                v = (data[off + y] >> b) & 1
            else:
                v = 0
                for p in range(bpp):
                    v |= ((data[off + (p // 2) * rows * 2 + y * 2 + (p & 1)] >> b) & 1) << p
            r.append(v)
        out.append(r)
    return out


def encode(pixels, bpp):
    """Inverse of decode for a rows x 8 pixel list."""
    rows = len(pixels)
    out = bytearray(tile_size(bpp, rows))
    for y, r in enumerate(pixels):
        for x, v in enumerate(r):
            b = 7 - x
            if bpp == 1:
                out[y] |= (v & 1) << b
                continue
            for p in range(bpp):
                if v >> p & 1:
                    out[(p // 2) * rows * 2 + y * 2 + (p & 1)] |= 1 << b
    return bytes(out)


def gray(bpp):
    """Index -> grey level, 0 is white (paper) and the top index black."""
    top = (1 << bpp) - 1
    return [255 - v * 255 // top for v in range(top + 1)]


def sheet(tiles, cols=16, scale=2, gap=1, palette=None, bg=160):
    """Grid of decoded tiles as an 'L' (or 'RGB' when palette entries are tuples) image."""
    if not tiles:
        raise ValueError("no tiles")
    h = len(tiles[0])
    if palette is None:
        top = max(max(max(r) for r in t) for t in tiles)
        palette = gray(max(1, top.bit_length()))
    mode = "RGB" if isinstance(palette[0], tuple) else "L"
    if mode == "RGB" and not isinstance(bg, tuple):
        bg = (bg, bg, bg)
    cw, ch = 8 + gap, h + gap
    rows = (len(tiles) + cols - 1) // cols
    img = Image.new(mode, (cols * cw, rows * ch), bg)
    px = img.load()
    for t, pix in enumerate(tiles):
        ox, oy = (t % cols) * cw, (t // cols) * ch
        for y, r in enumerate(pix):
            for x, v in enumerate(r):
                px[ox + x, oy + y] = palette[v % len(palette)]
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return img


def render(data, start, count, bpp, rows=8, stride=None, cols=16, scale=2, tall=False, palette=None):
    """Sheet of `count` tiles at `start`. `stride` overrides bytes per tile;
    `tall` stacks tile pairs into 8x16 glyphs (VRAM font layout)."""
    stride = stride or tile_size(bpp, rows)
    if start + count * stride > len(data):
        count = max(0, (len(data) - start) // stride)
    tiles = [decode(data, start + i * stride, bpp, rows) for i in range(count)]
    if tall:
        tiles = [tiles[i] + tiles[i + 1] for i in range(0, len(tiles) - 1, 2)]
    return sheet(tiles, cols=cols, scale=scale, palette=palette)
