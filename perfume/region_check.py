"""Crop every review region (from the review .md) out of the photo and the renders, side by side.

    python3 region_check.py review=reconstruction_feedback_iteration_4_review.md dir=gate5 out=gate5_regions
"""
import os
import re
import sys

from PIL import Image, ImageDraw

A = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
md = open(A.get("review", "reconstruction_feedback_iteration_4_review.md")).read()
D, OUT = A.get("dir", "."), A.get("out", "regions")
os.makedirs(OUT, exist_ok=True)
VIEWS = {"Front": "front", "Three-quarter": "three_quarter", "Top": "top", "Neck": "neck"}
view, notes = None, []
for line in md.splitlines():
    m = re.match(r"## (\S+) —", line)
    if m:
        view = VIEWS.get(m.group(1))
    m = re.match(r"(\d+)\. \*\*.*?\*\* (.*)", line)
    if m and view:
        notes.append([view, int(m.group(1)), m.group(2), None])
    m = re.search(r"centre \(([\d.]+), ([\d.]+)\), half-size ([\d.]+) × ([\d.]+)", line)
    if m and notes and notes[-1][3] is None:
        notes[-1][3] = tuple(map(float, m.groups()))
for v, k, text, (cx, cy, rx, ry) in notes:
    tiles = []
    for src in (f"ref_{v}.png", f"{D}/lux_{v}.png", f"{D}/clay_{v}.png"):
        if not os.path.exists(src):
            continue
        im = Image.open(src).convert("RGB")
        W, H = im.size
        px, py = max(rx * 1.35, 0.06), max(ry * 1.35, 0.06)
        box = (int(max(0, cx - px) * W), int(max(0, cy - py) * H), int(min(1, cx + px) * W), int(min(1, cy + py) * H))
        c = im.crop(box)
        s = 640 / c.width
        c = c.resize((640, int(c.height * s)), Image.LANCZOS)
        e = [((cx - rx) * W - box[0]) * s, ((cy - ry) * H - box[1]) * s, ((cx + rx) * W - box[0]) * s, ((cy + ry) * H - box[1]) * s]
        ImageDraw.Draw(c).ellipse(e, outline=(0, 200, 230), width=2)
        tiles.append(c)
    h = max(t.height for t in tiles)
    out = Image.new("RGB", (650 * len(tiles), h + 28), "white")
    ImageDraw.Draw(out).text((6, 8), f"{v} {k}: {text[:150]}   [photo | final | clay]", fill=(0, 0, 0))
    for i, t in enumerate(tiles):
        out.paste(t, (i * 650, 28))
    out.save(f"{OUT}/{v}_{k}.png")
print(len(notes), "regions ->", OUT)
