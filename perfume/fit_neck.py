"""Neck close-up camera from landmarks (silhouette overlap can't see the low elevation): actuator top centre and
width, flange centre and width, the bottle's front corner. Photo pixels measured on ref_neck (1800 x 2250)."""
import json
import math

import numpy as np
from scipy.optimize import least_squares

W, H = 1800, 2250
pump, collar, glass = (np.load(f"mesh/{n}.npz")["points"] for n in ("pump", "collar", "glass_full"))
act_top = pump[:, 2].max()
act_r = np.hypot(pump[:, 0], pump[:, 1])[pump[:, 2] > act_top - 0.5].max()
fl_r = np.hypot(collar[:, 0], collar[:, 1]).max()
fl_z = collar[np.hypot(collar[:, 0], collar[:, 1]) > fl_r - 0.3][:, 2].mean()
gx, gy, gz = glass[:, 0].max(), glass[:, 1].min(), np.percentile(glass[:, 2], 99.5)
body_top = glass[(np.abs(glass[:, 0]) > gx - 3) & (np.abs(glass[:, 1]) > -gy - 3)][:, 2].max()
corner = np.array([gx - 1.5, gy + 1.5, body_top - 1.0])     # front-right vertical edge, just under its top round
PHOTO = {"act": (903, 437, 355), "fl": (890, 1060, 830), "corner": (912, 1625)}


def cam(p):
    az, el, dist, tx, ty, tz = p
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    eye = np.array([tx, ty, tz]) + d * dist
    f = -d
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    focal = (H / 2) / (18 / 100)
    return eye, f, r, u, focal


def proj(p, X):
    eye, f, r, u, focal = cam(p)
    rel = np.atleast_2d(X) - eye
    return np.stack([W / 2 + focal * (rel @ r) / (rel @ f), H / 2 - focal * (rel @ u) / (rel @ f)], axis=1)


def ring(z, rad, n=72):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.stack([rad * np.cos(t), rad * np.sin(t), np.full(n, z)], axis=1)


def resid(p):
    out = []
    for key, z, rad in (("act", act_top, act_r), ("fl", fl_z, fl_r)):
        uv = proj(p, ring(z, rad))
        cx, cy, wid = PHOTO[key]
        ratio = 0.35 if key == "act" else 0.385
        out += [(uv[:, 0].mean() - cx) / 10, ((uv[:, 1].min() + uv[:, 1].max()) / 2 - cy) / 10, (np.ptp(uv[:, 0]) - wid) / 10,
                (np.ptp(uv[:, 1]) / np.ptp(uv[:, 0]) - ratio) * 60]   # the ellipse ratio fixes the elevation
    c = proj(p, corner)[0]
    out += [(c[0] - PHOTO["corner"][0]) / 10, (c[1] - PHOTO["corner"][1]) / 10]
    return out


x0 = np.array([-45.0, 22.0, 200.0, 0.0, 0.0, act_top - 15])
res = least_squares(resid, x0, bounds=([-90, 5, 60, -30, -30, 0], [0, 80, 1200, 30, 30, 140]))
p = res.x
print("neck camera: az %.1f el %.1f dist %.0f target %s   rms %.1f px" % (p[0], p[1], p[2], np.round(p[3:], 1).tolist(),
                                                                         10 * np.sqrt(np.mean(np.square(res.fun)))))
for key, z, rad in (("act", act_top, act_r), ("fl", fl_z, fl_r)):
    uv = proj(p, ring(z, rad))
    print(f"  {key}: ellipse ratio {np.ptp(uv[:, 1]) / np.ptp(uv[:, 0]):.2f} (photo {0.35 if key == 'act' else 0.385})")
poses = json.load(open("poses.json"))
poses["neck"] = {"az": float(p[0]), "el": float(p[1]), "dist": float(p[2]), "target": [float(v) for v in p[3:]],
                 "method": "landmarks (fit_neck.py)", "rms_px": float(10 * np.sqrt(np.mean(np.square(res.fun))))}
json.dump(poses, open("poses.json", "w"), indent=1)
