"""Trace the Triomphe emblem from the top photo into clean, symmetric groove polygons for keel.

    python3 trace_emblem.py  ->  emblem.json, emblem_trace.png

The cap top in ref_top is black lacquer; the emblem shows as thin bright contour lines, the edges of a shallow relief.
1. the cap: the dark region (filled); its interior, eroded off the rim
2. the lines: bright pixels inside it
3. regions: the pieces of the interior that the lines separate. The background is the one touching the rim; a
   region is a stroke (C, central frame) if it borders the background, a hole (the two triangles) if it borders only
   strokes
4. strokes minus holes, plus the line width, symmetrised left/right and top/bottom (the motif is), smoothed
5. contours -> simplified polygons in cap units: the cap is 909 px across its flats in the photo = 2 R cos 15 deg
Coordinates are centred on the cap, x to the right, y up (image up = the back of the bottle in the top view).
"""
import json
import math

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes, gaussian_filter, label
from skimage.measure import approximate_polygon, find_contours

CAP_R = 20.0                                     # parade.py drawing units (circumradius of the 12-sided cap)
ACROSS_FLATS = 2 * CAP_R * math.cos(math.radians(15))

g = np.asarray(Image.open("ref_top.png").convert("L")).astype(float)
dark = binary_fill_holes(g < 45)
lab, n = label(dark)
cap = lab == np.bincount(lab.ravel())[1:].argmax() + 1
ys, xs = np.nonzero(cap)
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
px = ACROSS_FLATS / (x1 - x0)                   # drawing units per pixel
inner = binary_erosion(cap, iterations=45)

lines = (g > 55) & inner
S = (slice(int(cy) - 460, int(cy) + 460), slice(int(cx) - 460, int(cx) + 460))
m = lines[S]
m = m | m[:, ::-1] | m[::-1, :] | m[::-1, ::-1]   # symmetrise about the cap centre lines (the motif is symmetric)
m = binary_dilation(m, iterations=3)
from skimage.morphology import remove_small_objects, skeletonize  # noqa: E402
skel = skeletonize(m)
skel = remove_small_objects(skel, 60, connectivity=2)
GROOVE = 0.35                                    # groove width, drawing units
band = binary_dilation(skel, iterations=max(1, int(round(GROOVE / px / 2))))
sub = gaussian_filter(band.astype(float), 1.5)
loops = []
for c in find_contours(sub, 0.5):
    c = approximate_polygon(c, tolerance=0.9)
    if len(c) < 6:
        continue
    pts = [((p[1] - 460) * px, -(p[0] - 460) * px) for p in c[:-1]]
    area = 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if abs(area) < 0.02:
        continue
    loops.append({"pts": [[round(x, 4), round(y, 4)] for x, y in pts], "area": round(area, 3)})
# outer loops vs holes: a loop inside another loop is a hole of it
def inside(p, poly):
    x, y = p
    c = False
    for (xa, ya), (xb, yb) in zip(poly, poly[1:] + poly[:1]):
        if (ya > y) != (yb > y) and x < xa + (y - ya) * (xb - xa) / (yb - ya):
            c = not c
    return c


shapes = []
for i, lp in enumerate(loops):
    parents = [j for j, other in enumerate(loops) if j != i and abs(other["area"]) > abs(lp["area"]) and inside(lp["pts"][0], other["pts"])]
    lp["depth"] = len(parents)
for i, lp in enumerate(loops):
    if lp["depth"] % 2 == 0:
        holes_ = [o["pts"] for o in loops if o["depth"] == lp["depth"] + 1 and inside(o["pts"][0], lp["pts"])]
        shapes.append({"outer": lp["pts"], "holes": holes_})
ext = np.array([p for s in shapes for p in s["outer"]])
print(f"{len(shapes)} stroke shapes, {sum(len(s['holes']) for s in shapes)} holes; extent x +-{abs(ext[:, 0]).max():.2f} "
      f"y +-{abs(ext[:, 1]).max():.2f} (cap across flats {ACROSS_FLATS:.2f})")
json.dump({"units": "parade.py drawing units, cap centre, x right, y up", "cap_across_flats": ACROSS_FLATS, "shapes": shapes},
          open("emblem.json", "w"), indent=0)
# check image: the traced shapes over the photo crop
crop = Image.open("ref_top.png").convert("RGB").crop((int(cx) - 460, int(cy) - 460, int(cx) + 460, int(cy) + 460))
from PIL import ImageDraw  # noqa: E402
dr = ImageDraw.Draw(crop)
for s in shapes:
    for loop, col in [(s["outer"], (255, 40, 40))] + [(h, (40, 200, 255)) for h in s["holes"]]:
        q = [(x / px + 460, -y / px + 460) for x, y in loop]
        dr.line(q + q[:1], fill=col, width=3)
crop.save("emblem_trace.png")
print("emblem.json, emblem_trace.png")
