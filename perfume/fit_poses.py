"""Fit each render camera to its reference photo by silhouette overlap.

    python3 fit_poses.py  ->  poses.json (one camera per view), pose_fit.png (overlays: photo | fitted silhouette)

The bottle's silhouette in a photo: everything that differs from the even backdrop, holes filled. The model's: the
keel meshes (glass, cap, collar, pump) projected through the renderers' camera (100 mm lens, 36 mm on the long side,
looking at a target, Z up) and filled. Nelder-Mead on 1 - IoU over azimuth, elevation, distance and the target,
starting from the hand-set views. The neck close-up is cropped by its frame, which IoU handles as it is.
"""
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import binary_fill_holes, label
from scipy.optimize import minimize

W, H = 360, 450                                   # working resolution (the photos are 4:5)
VIEWS = {  # name: (azimuth deg, elevation deg, distance mm, target xyz mm) -- the starting guesses
    "front": (-90.0, 3.4, 395.0, (0.0, 0.0, 56.0)),
    "three_quarter": (-60.0, 21.0, 400.0, (0.0, 0.0, 50.0)),
    "top": (-90.0, 89.9, 290.0, (0.0, 0.0, 60.0)),
    "neck": (-48.4, 38.0, 150.0, (2.0, 0.0, 92.0)),
}


def load(name):
    return np.load(f"mesh/{name}.npz")["points"]


PARTS = {v: [load(n) for n in (("glass_full", "collar", "pump") if v == "neck" else ("glass_full", "cap", "collar"))]
         for v in VIEWS}                                   # each part is near convex in projection: its hull is exact


def photo_mask(view):
    im = np.asarray(Image.open(f"ref_{view}.png").convert("RGB").resize((W, H), Image.LANCZOS)).astype(float)
    border = np.concatenate([im[:8].reshape(-1, 3), im[-8:].reshape(-1, 3), im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    diff = np.abs(im - bg).max(axis=2)
    sat = im.max(axis=2) - im.min(axis=2)
    # gold and glass edges are saturated, the cap dark, the label bright; the floor shadow is neutral and only a
    # little darker, so it stays out
    m = (sat > (40 if view == "top" else 25)) | (diff > 40)
    m = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))) > 0
    m = binary_fill_holes(m)
    lab, n = label(m)
    if n:                                                     # the bottle is the largest piece; the soft floor
        sizes = np.bincount(lab.ravel())[1:]                   # shadow, when it separates, is dropped
        m = lab == 1 + int(np.argmax(sizes))
    return m


def project(pts, az, el, dist, tgt):
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    eye = np.array(tgt) + d * dist
    f = -d                                                    # forward
    up = np.array([0, 0, 1.0]) if abs(f[2]) < 0.999 else np.array([0, 1.0, 0])
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    rel = pts - eye
    x, y, z = rel @ r, rel @ u, rel @ f
    focal = (H / 2) / (18 / 100)                               # 100 mm lens, 36 mm sensor on the long (vertical) side
    return np.stack([W / 2 + focal * x / z, H / 2 - focal * y / z], axis=1)


from scipy.spatial import ConvexHull  # noqa: E402


def model_mask(view, p):
    """union of the parts' projected convex hulls (splatting vertices left the big flat faces hollow)"""
    az, el, dist, tx, ty, tz = p
    img = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(img)
    for pts in PARTS[view]:
        uv = project(pts[:: max(1, len(pts) // 6000)], az, el, dist, (tx, ty, tz))
        uv = uv[np.isfinite(uv).all(axis=1)]
        if len(uv) < 3:
            continue
        hull = uv[ConvexHull(uv).vertices]
        dr.polygon([tuple(q) for q in hull], fill=255)
    return np.asarray(img) > 0


def iou(a, b):
    return (a & b).sum() / max((a | b).sum(), 1)


poses, tiles = {}, []
for view, (az, el, dist, tgt) in VIEWS.items():
    ref = photo_mask(view)
    x0 = np.array([az, el, dist, *tgt], float)
    cost = lambda p: 1 - iou(model_mask(view, p), ref)  # noqa: E731
    if view == "top":                                          # straight down: elevation stays at the pole
        res = minimize(lambda q: cost(np.array([q[0], el, q[1], q[2], q[3], tgt[2]])), [az, dist, tgt[0], tgt[1]],
                       method="Nelder-Mead", options={"xatol": 0.05, "fatol": 1e-4, "maxiter": 400})
        p = np.array([res.x[0], el, res.x[1], res.x[2], res.x[3], tgt[2]])
    else:
        simplex = np.vstack([x0, x0 + np.diag([6.0, 4.0, 30.0, 4.0, 4.0, 6.0])])   # steps big enough to escape the guess
        res = minimize(cost, x0, method="Nelder-Mead",
                       options={"xatol": 0.05, "fatol": 1e-4, "maxiter": 800, "initial_simplex": simplex})
        p = res.x
    before, after = 1 - cost(x0), 1 - cost(p)
    print(f"{view:14s} IoU {before:.3f} -> {after:.3f}   az {p[0]:.1f} el {p[1]:.1f} dist {p[2]:.0f} target {np.round(p[3:], 1).tolist()}")
    poses[view] = {"az": float(p[0]), "el": float(p[1]), "dist": float(p[2]), "target": [float(v) for v in p[3:]],
                   "iou_before": float(before), "iou_after": float(after)}
    photo = Image.open(f"ref_{view}.png").convert("RGB").resize((W, H))
    over = np.asarray(photo).astype(float)
    mm = model_mask(view, p)
    edge = mm ^ binary_fill_holes(np.asarray(Image.fromarray(mm.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3))) > 0)
    over[edge] = [255, 0, 0]
    tiles.append(Image.fromarray(over.astype(np.uint8)))
json.dump(poses, open("poses.json", "w"), indent=1)
sheet = Image.new("RGB", (W * 4, H), "white")
for i, t in enumerate(tiles):
    sheet.paste(t, (i * W, 0))
sheet.save("pose_fit.png")
print("poses.json, pose_fit.png")
