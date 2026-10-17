"""Label textures for the bottle (parade.py: LW x LH drawing units), 20 px per unit.

    python3 make_label.py  ->  label_print.png (ink, black on transparent), label_bump.png (paper relief)

print: the photo's own letterforms. The paper label in ref_front (front, near-orthographic) spans x 670..1136,
y 906..1544; inside it the ink is the dark pixels. The ink mask is lifted straight from that crop (anti-aliased by a
soft threshold), so CELINE / PARADE / PARIS keep their exact shapes, weights, tracking and spacing.
bump: irregular paper grain at three scales (0.05 to 0.2 units, no regular weave) plus the embossed border as a
soft, low ridge about 3 units in from the edge, on all four sides.
"""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

PX = 40                                          # 2x: small lines keep their weight
LW, LH = 39.2, 55.4                              # parade.py: LW, LH
W, H = round(LW * PX), round(LH * PX)

crop = Image.open("ref_front.png").convert("L").crop((676, 906, 1128, 1546)).resize((W, H), Image.LANCZOS)
g = np.asarray(crop).astype(float)
paper = np.median(g)
ink = np.clip((paper - 28 - g) / 120, 0, 1)      # paper ~235 -> 0, letter cores -> 1; a lower threshold than before
#                                                 keeps PARADE / PARIS at their weight; the grain (<25 below paper) stays out
ink[ink < 0.08] = 0
ink[:, :24] = ink[:, -24:] = 0                   # the crop's edges catch the glass rim, not print
ink[:24] = ink[-24:] = 0
keep = np.zeros_like(ink)                        # only the text block: the frame's shadow lines are relief, not ink
keep[int(0.33 * H):int(0.67 * H), int(0.12 * W):int(0.88 * W)] = 1
ink *= keep
# the embossed border's double line (iteration 6). It shows in every photo as two thin grey lines ~0.6 apart, 2.2-2.9
# units in from the paper edge at the sides (ref_front rows 1000/1300: dips to ~200 on a ~240 paper, 7 px apart).
# Iteration 4 cut it out of the print as "shadow lines, not ink"; the raised geometry alone never showed it under the
# frontal light, so the lines are lifted from the photo again: fine detail darker than its surroundings, in the band
# between the glass rim and the text block, at the photo's own darkness (~15 %).
# measured on directional averages of the crop (grain averaged out along each side; peaks of the local darkening):
# two framed pairs of crisp lines, each pair 0.6 apart. Outer pair ~2.0 / 2.6 in from the crop edges (strongest on the
# sides: contrast ~30 left, ~9 bottom), inner pair (the embossed panel's edge) ~3.9 / 4.45 in (strongest at the top,
# ~8). Drawn symmetric about the crop (the text block is centred in it), as clean rectangles.
yy0, xx0 = np.mgrid[0:H, 0:W].astype(float) / PX
LINE_W = 0.16                                       # units (0.11 is ~1 px in the finals: filtered to a faint grey)
lines = np.zeros((H, W))
for inset, a_side, a_tb in ((2.0, 0.42, 0.24), (2.6, 0.42, 0.24), (3.9, 0.26, 0.26), (4.45, 0.26, 0.26)):
    x0, y0, x1, y1 = inset, inset, LW - inset, LH - inset
    span_y = (yy0 >= y0) & (yy0 <= y1)
    span_x = (xx0 >= x0) & (xx0 <= x1)
    vert = span_y & ((np.abs(xx0 - x0) < LINE_W / 2) | (np.abs(xx0 - x1) < LINE_W / 2))
    horz = span_x & ((np.abs(yy0 - y0) < LINE_W / 2) | (np.abs(yy0 - y1) < LINE_W / 2))
    lines = np.maximum(lines, a_side * vert)
    lines = np.maximum(lines, a_tb * horz)
lines = gaussian_filter(lines, 0.03 * PX)           # anti-aliased edges
ink = np.maximum(ink, lines)
print("border lines: coverage", round(float((lines > 0.05).mean() * 100), 2), "%")
rgba = np.zeros((H, W, 4), np.uint8)
rgba[..., 3] = (ink * 255).astype(np.uint8)
Image.fromarray(rgba, "RGBA").save("label_print.png")
print("label_print.png", (W, H), f"ink coverage {ink.mean() * 100:.1f}%")

rng = np.random.default_rng(7)


def noise(scale):
    n = gaussian_filter(rng.normal(size=(H, W)), scale * PX)
    return n / n.std()


grain = 0.5 * noise(0.05) + 0.35 * noise(0.12) + 0.15 * noise(0.2)
grain = 0.5 + 0.18 * grain / np.abs(grain).max() * 2
yy, xx = np.mgrid[0:H, 0:W].astype(float) / PX
inset = np.minimum.reduce([xx - 3, (W / PX - 3) - xx, yy - 3, (H / PX - 3) - yy])
relief = grain + 0.18 * np.exp(-(inset / 0.5) ** 2)
Image.fromarray((np.clip(relief, 0, 1) * 255).astype(np.uint8)).save("label_bump.png")
print("label_bump.png", (W, H))
