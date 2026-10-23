"""Compare screenshots as text, so an image only needs to be looked at when it differs."""
import glob
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def region(im, box):
    return im.crop((box[0], box[1], box[0] + box[2], box[1] + box[3])) if box else im


def compare(a_path, b_path, box=None, tol=0):
    """(bbox or None, message). bbox is in full-image coordinates."""
    a = region(Image.open(a_path).convert("RGB"), box)
    b = region(Image.open(b_path).convert("RGB"), box)
    if a.size != b.size:
        return None, f"size {a.size} != {b.size}"
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > tol else 0)
    bbox = diff.getbbox()
    if not bbox:
        return None, "same"
    n = diff.histogram()[255]
    if box:
        bbox = (bbox[0] + box[0], bbox[1] + box[1], bbox[2] + box[0], bbox[3] + box[1])
    return bbox, f"diff px={n} bbox={bbox[0]},{bbox[1]},{bbox[2] - bbox[0]},{bbox[3] - bbox[1]}"


def pairs(actual, ref):
    """ACTUAL/REF may be files or directories (PNG files matched by name)."""
    act, ref = Path(actual), Path(ref)
    if act.is_dir():
        return [(f, ref / f.name) for f in sorted(act.glob("*.png")) if f.name != "contact.png"]
    return [(act, ref)]


def contact(pattern, out, cols=10, scale=0.5, label=10):
    """Contact sheet of the files matching a glob, each labelled with its name."""
    fs = sorted(glob.glob(pattern))
    if not fs:
        raise ValueError(f"no files match {pattern}")
    w, h = int(256 * scale), int(224 * scale)
    im = Image.new("RGB", (cols * w, ((len(fs) + cols - 1) // cols) * (h + label)), "gray")
    d = ImageDraw.Draw(im)
    for i, f in enumerate(fs):
        x, y = (i % cols) * w, (i // cols) * (h + label)
        im.paste(Image.open(f).convert("RGB").resize((w, h)), (x, y + label))
        d.text((x + 2, y), Path(f).stem, fill="white")
    im.save(out)
    return len(fs)
