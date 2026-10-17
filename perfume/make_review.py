"""Review sheets for an iteration: photo vs render, all views, plus matched component crops.

    python3 make_review.py [prefix=lux]  ->  compare_photo_vs_<prefix>.png, components_<prefix>.png

Component crops are taken relative to the bottle bounding box found on the photo; the render (camera fitted to the
photo) is cut at the same relative image position, so both crops have the same shape.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_fill_holes, label

PREFIX = dict(a.split("=") for a in sys.argv[1:] if "=" in a).get("prefix", "lux")
VIEWS = ("front", "three_quarter", "neck", "top")


def bottle_box(im):
    a = np.asarray(im.convert("RGB")).astype(float)
    border = np.concatenate([a[:6].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    m = binary_fill_holes(np.abs(a - bg).max(axis=2) > 22)
    lab, n = label(m)
    if not n:
        return 0, 0, im.width, im.height
    k = np.bincount(lab.ravel())[1:].argmax() + 1
    ys, xs = np.nonzero(lab == k)
    return xs.min(), ys.min(), xs.max(), ys.max()


def rel_crop(im, box_rel, size, box_from=None):
    """box_from: image to locate the bottle on (same camera), e.g. the final for a clay render whose grey bottle
    doesn't separate from the grey backdrop."""
    if box_from is None:
        x0, y0, x1, y1 = bottle_box(im)
    else:
        sx, sy = im.width / box_from.width, im.height / box_from.height
        bx = bottle_box(box_from)
        x0, y0, x1, y1 = bx[0] * sx, bx[1] * sy, bx[2] * sx, bx[3] * sy
    w, h = x1 - x0, y1 - y0
    rx0, ry0, rx1, ry1 = box_rel
    c = im.crop((int(x0 + rx0 * w), int(y0 + ry0 * h), int(x0 + rx1 * w), int(y0 + ry1 * h)))
    return fit(c, size)


def fit(im, size):
    """Uniform scale into size, centred on the backdrop colour (keeps the aspect ratio)."""
    k = min(size[0] / im.width, size[1] / im.height)
    r = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    bg = tuple(int(c) for c in np.median(np.asarray(im)[:4].reshape(-1, 3), axis=0))
    out = Image.new("RGB", size, bg)
    out.paste(r, ((size[0] - r.width) // 2, (size[1] - r.height) // 2))
    return out


# four views
tiles = []
for v in VIEWS:
    tiles += [fit(Image.open(f"ref_{v}.png").convert("RGB"), (400, 500)), fit(Image.open(f"{PREFIX}_{v}.png").convert("RGB"), (400, 500))]
sheet = Image.new("RGB", (1600, 1000), "white")
for k, t in enumerate(tiles):
    sheet.paste(t, ((k % 4) * 400, (k // 4) * 500))
sheet.save(f"compare_photo_vs_{PREFIX}.png")

# components: (name, view, box relative to the bottle bbox)
COMP = [("cap", "front", (0.05, 0.0, 0.95, 0.30)),
        ("label", "front", (0.15, 0.30, 0.85, 0.80)),
        ("base", "three_quarter", (0.0, 0.62, 1.0, 1.0)),
        ("emblem", "top", (0.18, 0.18, 0.82, 0.82)),
        ("atomizer", "neck", (0.15, 0.0, 0.85, 0.55)),
        ("shoulder", "three_quarter", (0.0, 0.12, 1.0, 0.45))]
rows = []
for name, v, box in COMP:
    ph = rel_crop(Image.open(f"ref_{v}.png").convert("RGB"), box, (420, 300))
    # renders use cameras fitted to the photos: cut them at the photo's bottle box (render-side detection is
    # thrown off by the dark flags and the shadow reaching the frame edge, and by the grey clay on grey)
    rd = rel_crop(Image.open(f"{PREFIX}_{v}.png").convert("RGB"), box, (420, 300), Image.open(f"ref_{v}.png"))
    row = Image.new("RGB", (860, 330), "white")
    row.paste(ph, (0, 30))
    row.paste(rd, (440, 30))
    ImageDraw.Draw(row).text((6, 8), f"{name} ({v}): photo | render", fill=(0, 0, 0))
    rows.append(row)
comp = Image.new("RGB", (860 * 2, 330 * 3), "white")
for k, r in enumerate(rows):
    comp.paste(r, ((k % 2) * 860, (k // 2) * 330))
comp.save(f"components_{PREFIX}.png")
print(f"compare_photo_vs_{PREFIX}.png, components_{PREFIX}.png")
