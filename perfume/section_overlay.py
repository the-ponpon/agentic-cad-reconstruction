"""Gate A check: model sections drawn over the photos, through the fitted cameras.

    python3 section_overlay.py  ->  sections.png

front: the glass (white) and liquid (red) cut by the plane y = 0, projected into ref_front. The cut sits mid-depth,
so through the thick front glass the photo shows the gold edge refracted a little; wall thickness, shoulder rise,
floor arch and cap seat are compared directly. top: the cut at mid-height into ref_top (outer square and cavity).
"""
import json
import math

import numpy as np
from PIL import Image, ImageDraw


POSES = json.load(open("poses.json"))


def mesh(name):
    m = np.load(f"mesh/{name}.npz")
    return m["points"], m["tris"]


def cut(pts, tris, axis, value):
    """segments where the triangles cross the plane coordinate[axis] = value"""
    d = pts[tris][:, :, axis] - value
    segs = []
    for tri, dd in zip(pts[tris], d):
        s = np.sign(dd)
        if s.max() <= 0 or s.min() >= 0:
            continue
        hit = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (dd[i] > 0) != (dd[j] > 0):
                t = dd[i] / (dd[i] - dd[j])
                hit.append(tri[i] + t * (tri[j] - tri[i]))
        if len(hit) == 2:
            segs.append(hit)
    return np.array(segs)


def project(view, X, W, H):
    p = POSES[view]
    az, el, dist, tgt = p["az"], p["el"], p["dist"], np.array(p["target"])
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    eye = tgt + d * dist
    f = -d
    up = np.array([0, 0, 1.0]) if abs(f[2]) < 0.999 else np.array([0, 1.0, 0])
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    focal = (H / 2) / (18 / 100)
    rel = X - eye
    return np.stack([W / 2 + focal * (rel @ r) / (rel @ f), H / 2 - focal * (rel @ u) / (rel @ f)], axis=-1)


tiles = []
info = json.load(open("parade_parts.json"))
for view, axis, value in (("front", 1, 0.0), ("top", 2, info["cavity"][2] + 0.5 * (info["cavity"][3] - info["cavity"][2]))):
    im = Image.open(f"ref_{view}.png").convert("RGB")
    W, H = im.size
    dr = ImageDraw.Draw(im)
    gp = mesh("glass_full")[0]
    gw = gp[:, 0].max() - gp[:, 0].min()
    for name, colour in (("glass_full", (0, 60, 255)), ("liquid", (255, 0, 0)), ("cap", (0, 200, 120)), ("collar", (0, 200, 120))):
        segs = cut(*mesh(name), axis, value)
        if not len(segs):
            continue
        X = segs.reshape(-1, 3)
        if view == "front":   # near-orthographic photo: scale to the 762 px body (x 519..1281), base on y = 1999
            sc = 762 / gw
            uv = np.stack([900 + X[:, 0] * sc, 1999 - X[:, 2] * sc], axis=1).reshape(-1, 2, 2)
        else:
            uv = project(view, X, W, H).reshape(-1, 2, 2)
        for (x0, y0), (x1, y1) in uv:
            dr.line([(x0, y0), (x1, y1)], fill=colour, width=3)
    tiles.append(im.resize((W // 2, H // 2)))
sheet = Image.new("RGB", (sum(t.width for t in tiles), tiles[0].height), "white")
x = 0
for t in tiles:
    sheet.paste(t, (x, 0))
    x += t.width
sheet.save("sections.png")
print("sections.png")
