"""A cut cherry-blossom branch lying on the counter, built as geometry (no reconstruction).

    import branch3d; branch3d.build(define, prop, opt)      (called by shop_set when branch=3d)

Units mm, the counter top at z = 0. Colours sampled from the reference photo (shop/props/blossom5_src.webp): petals
(224, 206, 214), bark (73, 49, 27), buds (200, 107, 122). The stem rests on the marble along its length (a cut
branch lies on its heaviest side); the twigs lift a little off it, the blossoms face up and out as they do on a
branch put down on a table: nothing goes below the counter.
"""
import math

import numpy as np


def _frame(t):
    t = t / (np.linalg.norm(t) + 1e-12)
    u = np.cross(t, [0, 0, 1.0]) if abs(t[2]) < 0.95 else np.cross(t, [1.0, 0, 0])
    u /= np.linalg.norm(u)
    return t, u, np.cross(t, u)


class M:
    def __init__(self):
        self.p, self.t = [], []

    def tube(self, pts, rad, n=10, cap=True):
        pts = np.asarray(pts, float)
        k0 = len(self.p)
        for i, c in enumerate(pts):
            t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            _, u, v = _frame(t)
            for j in range(n):
                a = 2 * math.pi * j / n
                self.p.append(c + rad[i] * (math.cos(a) * u + math.sin(a) * v))
        for i in range(len(pts) - 1):
            for j in range(n):
                a0, a1 = k0 + i * n + j, k0 + i * n + (j + 1) % n
                self.t += [(a0, a1 + n, a0 + n), (a0, a1, a1 + n)]
        if cap:                                                  # the clean cut at the thick end
            c0 = len(self.p); self.p.append(pts[0])
            for j in range(n):
                self.t.append((c0, k0 + (j + 1) % n, k0 + j))

    def ellipsoid(self, c, axis, r_ax, r_side, n=10):
        t, u, v = _frame(np.asarray(axis, float))
        k0 = len(self.p)
        for i in range(n + 1):
            th = math.pi * i / n
            for j in range(n):
                ph = 2 * math.pi * j / n
                self.p.append(np.asarray(c) + r_ax * math.cos(th) * t + r_side * math.sin(th) * (math.cos(ph) * u + math.sin(ph) * v))
        for i in range(n):
            for j in range(n):
                a0, a1 = k0 + i * n + j, k0 + i * n + (j + 1) % n
                self.t += [(a0, a1, a1 + n), (a0, a1 + n, a0 + n)]

    def petal(self, c, axis, out, length, width, cup, notch=0.18, nu=7, nv=5):
        """one petal: a cupped, slightly notched oval leaving the flower centre c along `out` (perpendicular-ish to the
        flower axis), curving up towards `axis`"""
        axis = np.asarray(axis, float) / np.linalg.norm(axis)
        out = np.asarray(out, float); out = out - axis * (out @ axis); out /= np.linalg.norm(out)
        side = np.cross(axis, out)
        k0 = len(self.p)
        for i in range(nu + 1):
            s = i / nu                                           # 0 at the centre, 1 at the tip
            half = width / 2 * math.sin(math.pi * min(1.0, 0.15 + 0.95 * s)) * (1 - 0.25 * s)
            for j in range(nv + 1):
                w = (j / nv - 0.5) * 2                           # -1 .. 1 across
                tip = length * s * (1 - notch * (1 - abs(w)) * s ** 6)   # the notched tip of a cherry petal
                lift = cup * (s ** 2) * length + 0.25 * cup * width * w * w   # curls up and cups across
                self.p.append(np.asarray(c) + out * tip + side * half * w + axis * lift)
        for i in range(nu):
            for j in range(nv):
                a = k0 + i * (nv + 1) + j
                self.t += [(a, a + 1, a + nv + 2), (a, a + nv + 2, a + nv + 1)]


def _bez(p0, p1, p2, n=24):
    s = np.linspace(0, 1, n)[:, None]
    return (1 - s) ** 2 * p0 + 2 * (1 - s) * s * p1 + s ** 2 * p2


def build(define, prop, opt):
    rng = np.random.default_rng(int(opt.get("branch_seed", 5)))
    ox, oy = float(opt.get("branch_x", 0.0)), float(opt.get("branch_y", 75.0))
    yaw = math.radians(float(opt.get("branch_yaw", -14.0)))
    L = float(opt.get("branch_len", 480.0))
    R = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
    bark, petals, centres, stamens, buds = M(), M(), M(), M(), M()

    # the main stem: lies on the marble, cut end on the right, thinning to the left
    r0 = 4.2
    stem = _bez(np.array([L / 2, 0, r0]), np.array([0, 14, r0]), np.array([-L / 2, -6, 2.2]), 40)
    rad = np.linspace(r0, 1.6, len(stem))
    stem[:, 2] = rad                                             # resting on its underside
    bark.tube(stem, rad, n=12)
    for k in range(9):                                           # knots / bud scars along the stem
        i = int(rng.integers(4, len(stem) - 4))
        bark.ellipsoid(stem[i] + [0, 0, rad[i] * 0.6], [0, 0, 1], rad[i] * 0.55, rad[i] * 0.75, n=6)

    def flower(c, up, size):
        up = np.asarray(up, float); up /= np.linalg.norm(up)
        _, u, v = _frame(up)
        a0 = rng.uniform(0, 2 * math.pi)
        for k in range(5):
            a = a0 + 2 * math.pi * k / 5 + rng.normal(0, 0.08)
            out = math.cos(a) * u + math.sin(a) * v
            petals.petal(c + up * 0.6, up, out, size * rng.uniform(0.9, 1.05), size * 0.92, cup=rng.uniform(0.18, 0.32))
        centres.ellipsoid(c + up * 1.0, up, 1.2, size * 0.18, n=8)
        for k in range(14):                                      # stamens: fine filaments with yellow anthers
            a = rng.uniform(0, 2 * math.pi); rr = size * rng.uniform(0.12, 0.22)
            base = c + up * 1.2 + rr * 0.3 * (math.cos(a) * u + math.sin(a) * v)
            tip = c + up * size * rng.uniform(0.38, 0.5) + rr * (math.cos(a) * u + math.sin(a) * v)
            stamens.tube([base, tip], [0.18, 0.15], n=4, cap=False)
            stamens.ellipsoid(tip, tip - base, 0.45, 0.35, n=5)

    # side twigs: leave the stem, lift off the marble a little, each ending in blossoms and buds
    n_tw = int(opt.get("branch_twigs", 11))
    for k in range(n_tw):
        f = 0.12 + 0.8 * (k + rng.uniform(-0.2, 0.2)) / n_tw
        i = int(f * (len(stem) - 1))
        base = stem[i].copy()
        side = 1 if k % 2 else -1
        d = np.array([-0.55 * rng.uniform(0.6, 1.0), side * rng.uniform(0.5, 0.9), 0.0])
        ln = rng.uniform(35, 70)
        p1 = base + d * ln * 0.5 + [0, 0, rng.uniform(6, 14)]
        p2 = base + d * ln + [0, 0, rng.uniform(10, 26)]
        tw = _bez(base, p1, p2, 12)
        bark.tube(tw, np.linspace(rad[i] * 0.55, 0.8, len(tw)), n=8, cap=False)
        # blossom cluster at the twig end, plus one along it; buds on short pedicels
        spots = [tw[-1]] * int(rng.integers(2, 4)) + ([tw[len(tw) // 2]] if rng.random() < 0.7 else [])
        for pt in spots:                                          # a cluster of 2-3 at the end, one along the twig
            up = np.array([rng.normal(0, 0.55), side * rng.uniform(0.1, 0.6) - 0.3, 1.0])
            ped = pt + up / np.linalg.norm(up) * rng.uniform(8, 16)
            bark.tube([pt, ped], [0.7, 0.5], n=6, cap=False)
            flower(ped, up, rng.uniform(13, 17))
        for j in range(int(rng.integers(1, 4))):
            q = tw[int(rng.integers(len(tw) // 2, len(tw)))]
            dirb = np.array([rng.normal(0, 0.6), rng.normal(0, 0.6), 1.0]); dirb /= np.linalg.norm(dirb)
            tipb = q + dirb * rng.uniform(5, 9)
            bark.tube([q, tipb], [0.5, 0.45], n=5, cap=False)
            buds.ellipsoid(tipb + dirb * 3.0, dirb, 3.6, 2.4, n=8)
    # a few blossoms directly on the stem (cherry flowers sit in clusters on short spurs)
    for k in range(int(opt.get("branch_spurs", 7))):
        i = int(rng.integers(6, len(stem) - 6))
        up = np.array([rng.normal(0, 0.3), rng.choice([-1, 1]) * rng.uniform(0.3, 0.7), 1.0])
        ped = stem[i] + up / np.linalg.norm(up) * (rad[i] + 7)
        bark.tube([stem[i], ped], [0.8, 0.6], n=6, cap=False)
        flower(ped, up, rng.uniform(12, 15))

    def mat(name, typ, **kw):
        prop(f"scene.materials.{name}.type", typ)
        for k_, v_ in kw.items():
            prop(f"scene.materials.{name}.{k_}", *v_) if isinstance(v_, (tuple, list)) else prop(f"scene.materials.{name}.{k_}", v_)

    srgb = lambda r, g, b: tuple(round((c / 255.0) ** 2.2, 4) for c in (r, g, b))
    mat("cb_bark", "glossy2", kd=srgb(73, 49, 27), ks=(0.03, 0.03, 0.03), uroughness=0.45, vroughness=0.45)
    # petals are thin: they pass light through, which is what makes them glow against a lit background
    mat("cb_petal", "mattetranslucent", kr=srgb(232, 214, 222), kt=srgb(236, 196, 210))
    if opt.get("branch_coat", "0") == "1":                       # a thin glossy clear coat, as on a lacquered display branch
        for base in ("cb_bark", "cb_petal"):
            prop(f"scene.materials.{base}_coat.type", "glossycoating")
            prop(f"scene.materials.{base}_coat.base", base)
            prop(f"scene.materials.{base}_coat.ks", 0.05, 0.05, 0.05)
            prop(f"scene.materials.{base}_coat.uroughness", 0.03)
            prop(f"scene.materials.{base}_coat.vroughness", 0.03)
    mat("cb_centre", "matte", kd=srgb(205, 95, 120))
    mat("cb_stamen", "matte", kd=srgb(222, 196, 120))
    mat("cb_bud", "matte", kd=srgb(200, 107, 122))
    off = np.array([ox, oy, 0.0])
    cs = "_coat" if opt.get("branch_coat", "0") == "1" else ""
    for name, m, mt in (("cb_bark", bark, "cb_bark" + cs), ("cb_petals", petals, "cb_petal" + cs), ("cb_centres", centres, "cb_centre"),
                        ("cb_stamens", stamens, "cb_stamen"), ("cb_buds", buds, "cb_bud")):
        p = np.asarray(m.p) * float(opt.get("branch_scale", 0.7)) @ R.T + off
        p[:, 2] = np.maximum(p[:, 2], 0.05)                       # nothing below the counter
        define(name + "_m", p, np.asarray(m.t, np.int64))
        prop(f"scene.objects.{name}.shape", name + "_m")
        prop(f"scene.objects.{name}.material", mt)
    print("branch3d:", len(bark.t) + len(petals.t) + len(centres.t) + len(stamens.t) + len(buds.t), "triangles", flush=True)
