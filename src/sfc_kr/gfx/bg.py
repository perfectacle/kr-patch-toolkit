"""Render a BG layer from VRAM/CGRAM dumps and report which VRAM it uses.

Addresses are VRAM word addresses as written to the PPU registers ($2107-$210C).
Only 32x32 tilemaps with 8x8 tiles are handled.
"""
from PIL import Image

from .tiles import tile_size


def bgr555(c):
    return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)


def palette(cgram):
    return [bgr555(cgram[i] | cgram[i + 1] << 8) for i in range(0, len(cgram) - 1, 2)]


def _entry(vram, tm, k):
    o = (tm + k * 2) & 0xFFFF
    return vram[o] | vram[(o + 1) & 0xFFFF] << 8


def render(vram, cgram, tilemap_word, chr_word, bpp, palbase=0, scale=3, backdrop=(255, 0, 255)):
    """256x256 image; colour 0 is left as `backdrop`. `palbase` is added to the CGRAM
    index (mode 0 gives each BG its own 32-colour range)."""
    pal = palette(cgram)
    tm, ch = tilemap_word * 2, chr_word * 2
    tb = tile_size(bpp)
    img = Image.new("RGB", (256, 256), backdrop)
    px = img.load()
    for ty in range(32):
        for tx in range(32):
            e = _entry(vram, tm, ty * 32 + tx)
            t, p, hf, vf = e & 0x3FF, (e >> 10) & 7, e >> 14 & 1, e >> 15 & 1
            base = (ch + t * tb) & 0xFFFF
            for y in range(8):
                yy = 7 - y if vf else y
                for x in range(8):
                    b = 7 - (7 - x if hf else x)
                    v = 0
                    for pl in range(bpp):
                        v |= ((vram[(base + (pl // 2) * 16 + yy * 2 + (pl & 1)) & 0xFFFF] >> b) & 1) << pl
                    if v:
                        px[tx * 8 + x, ty * 8 + y] = pal[(palbase + p * (1 << bpp) + v) % len(pal)]
    if scale != 1:
        img = img.resize((256 * scale, 256 * scale), Image.NEAREST)
    return img


def refs(vram, tilemap_word, chr_word, bpp):
    """Sorted tile numbers the tilemap references and the VRAM byte span they cover."""
    tm, ch = tilemap_word * 2, chr_word * 2
    ts = sorted({_entry(vram, tm, k) & 0x3FF for k in range(1024)})
    tb = tile_size(bpp)
    return ts, [(ch + t * tb) & 0xFFFF for t in ts]


def hits(vram, tilemap_word, chr_word, bpp, lo, hi):
    """(first byte, last byte, tile count) of referenced tiles inside VRAM bytes [lo, hi)."""
    ts, offs = refs(vram, tilemap_word, chr_word, bpp)
    tb = tile_size(bpp)
    inside = [o for o in offs if lo <= o < hi]
    if not inside:
        return None
    return min(inside), max(inside) + tb - 1, len(inside)
