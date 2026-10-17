"""Mesh set of the generated boutique (shop/perfume_shop.webp) for the novel views: plain meshes and materials.

    import shop_set; shop_set.build(define, prop, here)   (called by parade_lux.py with shop=1)

Units mm, bottle at the origin standing on the counter (top at z = 0), the front camera on -y. The room is laid out
as in shop/perfume_shop_2.webp (image x maps to world x at 3 mm per px, x = (px - 830) * 3): back wall 1.8 m behind
the bottle with three lit shelf niches in brass frames (their back panels carry the image's shelves with the bottles,
real glass shelves with LED strips in front), a panelled centre wall with two opal sconces, fluted pilasters, a tall
French window on the left showing the Paris street, low brass-fluted cabinets with marble tops under the niches.
"""
import math
import os

import numpy as np
from PIL import Image

FLOOR = -950.0                      # shop floor (the counter top is 0)
WALL_Y = 1800.0
ROOM_X = (-3500.0, 1700.0)
CEIL = 2200.0


class Mesh:
    def __init__(self):
        self.p, self.t, self.uv = [], [], []

    def quad(self, a, b, c, d, uv=((0, 1), (1, 1), (1, 0), (0, 0))):
        k = len(self.p)
        self.p += [a, b, c, d]
        self.uv += list(uv)
        self.t += [(k, k + 1, k + 2), (k, k + 2, k + 3)]

    def box(self, x0, x1, y0, y1, z0, z1):
        P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for f in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (3, 2, 1, 0)):
            self.quad(*[P[i] for i in f])

    def cyl(self, cx, cy, r, z0, z1, n=24, axis="z"):
        k = len(self.p)
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            if axis == "z":
                self.p += [(cx + r * math.cos(a), cy + r * math.sin(a), z0), (cx + r * math.cos(a), cy + r * math.sin(a), z1)]
            self.uv += [(i / n, 1), (i / n, 0)]
            if i:
                b = k + 2 * (i - 1)
                self.t += [(b, b + 2, b + 3), (b, b + 3, b + 1)]

    def tube(self, pts, r, n=8):
        """a tube along a polyline (radius r, or a list of radii)"""
        pts = np.asarray(pts, float)
        rs = r if hasattr(r, "__len__") else [r] * len(pts)
        k = len(self.p)
        for i, c in enumerate(pts):
            t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            t /= np.linalg.norm(t) + 1e-9
            u = np.cross(t, [0, 0, 1.0]) if abs(t[2]) < 0.9 else np.cross(t, [1.0, 0, 0])
            u /= np.linalg.norm(u)
            v = np.cross(t, u)
            for j in range(n):
                a = 2 * math.pi * j / n
                self.p.append(tuple(c + rs[i] * (math.cos(a) * u + math.sin(a) * v)))
                self.uv.append((j / n, i / max(1, len(pts) - 1)))
        for i in range(len(pts) - 1):
            for j in range(n):
                a0, a1 = k + i * n + j, k + i * n + (j + 1) % n
                b0, b1 = a0 + n, a1 + n
                self.t += [(a0, a1, b1), (a0, b1, b0)]

    def sphere(self, c, r, n=10):
        k = len(self.p)
        for i in range(n + 1):
            th = math.pi * i / n
            for j in range(n):
                ph = 2 * math.pi * j / n
                self.p.append((c[0] + r * math.sin(th) * math.cos(ph), c[1] + r * math.sin(th) * math.sin(ph), c[2] + r * math.cos(th)))
                self.uv.append((j / n, i / n))
        for i in range(n):
            for j in range(n):
                a0, a1 = k + i * n + j, k + i * n + (j + 1) % n
                b0, b1 = a0 + n, a1 + n
                self.t += [(a0, b0, b1), (a0, b1, a1)]


def px(x):
    return (x - SET_PX) * 3.0


# niches: image frame (x0, x1, y0, y1) of the lit back panel, the crop of the image it shows
SET_PX = 1090.0                           # the image column behind the bottle (niche 2)
NICHES = {"n1": (488, 688, 25, 610), "n2": (958, 1222, 0, 615), "n3": (1365, 1536, 0, 625)}
SHELF_Z = (354.0, 750.0, 1155.0)          # the image's glass shelves (y 472, 340, 205 px on niche 1)
NICHE_Z0 = -60.0                          # the cabinet top


def build(define, prop, here, opt):
    if opt.get("set", "wall5") == "wall5":
        return build_wall5(define, prop, here, opt)
    return build_v2(define, prop, here, opt)


def build_v2(define, prop, here, opt):
    sd = os.path.join(here, "shop")
    from PIL import ImageEnhance
    im = Image.open(os.path.join(sd, "perfume_shop_2.webp")).convert("RGB")
    from PIL import ImageEnhance
    for n, (a, b, c, d) in NICHES.items():                                # half-desaturated: the image is very warm
        ImageEnhance.Color(im.crop((a, c, b, d))).enhance(0.55).save(os.path.join(sd, f"{n}.png"))
    im.crop((105, 0, 300, 730)).save(os.path.join(sd, "window.png"))
    for t in (("marble_top", "marble_front") if opt.get("grey_marble", "0") == "1" else ()):                            # the counter's marble, greyed: it read peach
        ImageEnhance.Color(Image.open(os.path.join(sd, f"{t}.png")).convert("RGB")).enhance(0.1).save(os.path.join(sd, f"{t}_cool.png"))
        prop(f"scene.textures.{t.replace('marble_', 'm')}.file", os.path.join(sd, f"{t}_cool.png"))

    def mat(name, typ, **kw):
        prop(f"scene.materials.{name}.type", typ)
        for k, v in kw.items():
            if isinstance(v, (tuple, list)):
                prop(f"scene.materials.{name}.{k}", *v)
            else:
                prop(f"scene.materials.{name}.{k}", v)

    def emit(name, src, gain, tint=(1.0, 1.0, 1.0)):
        if isinstance(src, str):
            prop(f"scene.textures.{name}_t.type", "imagemap")
            prop(f"scene.textures.{name}_t.file", os.path.join(sd, src))
            prop(f"scene.textures.{name}_t.gamma", 2.2)
            src = f"{name}_t"
        mat(name, "matte", kd=(0, 0, 0), emission=src)
        prop(f"scene.materials.{name}.emission.gain", *[float(gain) * t for t in tint])

    mat("plaster", "matte", kd=(0.84, 0.85, 0.86))                       # warm ivory plaster
    mat("brass", "metal2", preset="gold", uroughness=0.15, vroughness=0.15)
    mat("shelfglass", "glass", kt=(0.95, 0.96, 0.93), kr=(0.9, 0.9, 0.9), interiorior=1.5)
    emit("led", (0.92, 0.96, 1.0), opt.get("led", 30.0))
    for n in NICHES:
        emit(n, f"{n}.png", opt.get("niche", 3.0), tint=(0.70, 0.88, 1.25))     # the image is very warm: cool it firmly
    emit("window", "window.png", opt.get("window", 5.0))
    emit("ceil_light", (0.86, 0.93, 1.0), opt.get("ceil", 28.0))
    emit("sconce", (0.97, 0.97, 0.95), opt.get("sconce", 40.0))

    def add(name, m, material):
        define(name + "_m", np.array(m.p, float), np.array(m.t, np.int64), None, m.uv)
        prop(f"scene.objects.{name}.shape", name + "_m")
        prop(f"scene.objects.{name}.material", material)

    x0, x1, Y = ROOM_X[0], ROOM_X[1], WALL_Y
    wx0, wx1, wz0, wz1 = px(105), px(300), NICHE_Z0 - 300, CEIL - 200        # the French window, on the back wall
    shell = Mesh()
    shell.quad((x0, -1500, FLOOR), (x1, -1500, FLOOR), (x1, Y, FLOOR), (x0, Y, FLOOR))                      # floor
    shell.quad((x0, -1500, CEIL), (x1, -1500, CEIL), (x1, Y, CEIL), (x0, Y, CEIL))                          # ceiling
    shell.quad((x1, -1500, FLOOR), (x1, Y, FLOOR), (x1, Y, CEIL), (x1, -1500, CEIL))                        # right
    shell.quad((x0, Y, FLOOR), (x0, -1500, FLOOR), (x0, -1500, CEIL), (x0, Y, CEIL))                        # left
    shell.quad((x1, -1500, FLOOR), (x0, -1500, FLOOR), (x0, -1500, CEIL), (x1, -1500, CEIL))                # front
    # back wall around the window opening
    shell.quad((x0, Y, FLOOR), (wx0, Y, FLOOR), (wx0, Y, CEIL), (x0, Y, CEIL))
    shell.quad((wx1, Y, FLOOR), (x1, Y, FLOOR), (x1, Y, CEIL), (wx1, Y, CEIL))
    shell.quad((wx0, Y, FLOOR), (wx1, Y, FLOOR), (wx1, Y, wz0), (wx0, Y, wz0))
    shell.quad((wx0, Y, wz1), (wx1, Y, wz1), (wx1, Y, CEIL), (wx0, Y, CEIL))
    # the wall is built out 250 mm around the niches (the niches are recessed into it)
    for a, b in ((px(300), px(478)), (px(698), px(948)), (px(1232), px(1355))):
        shell.box(a, b, Y - 250, Y, FLOOR, CEIL)
    add("shop_shell", shell, "plaster")
    win = Mesh()
    win.quad((wx0, Y + 60, wz0), (wx1, Y + 60, wz0), (wx1, Y + 60, wz1), (wx0, Y + 60, wz1))
    add("shop_window", win, "window")
    wf = Mesh()                                                             # white window frame and glazing bars
    for x in (wx0, (wx0 + wx1) / 2, wx1):
        wf.box(x - 25, x + 25, Y - 10, Y + 50, wz0, wz1)
    for z in (wz0, wz0 + 0.62 * (wz1 - wz0), wz1):
        wf.box(wx0, wx1, Y - 10, Y + 50, z - 25, z + 25)
    rail = Mesh()                                                           # the balcony's wrought-iron rail outside
    for i in range(int((wx1 - wx0) / 60)):
        rail.box(wx0 + 30 + i * 60 - 6, wx0 + 30 + i * 60 + 6, Y + 30, Y + 42, wz0, wz0 + 450)
    rail.box(wx0, wx1, Y + 26, Y + 46, wz0 + 440, wz0 + 470)
    mat("iron", "glossy2", kd=(0.03, 0.03, 0.03), ks=(0.04, 0.04, 0.04), uroughness=0.3, vroughness=0.3)
    add("shop_rail", rail, "iron")

    # fluted pilasters, and panel mouldings on the centre wall
    pil = Mesh()
    for pcx in (px(390), px(1285)):
        pil.box(pcx - 130, pcx + 130, Y - 330, Y - 250, FLOOR, CEIL - 120)
        for f in range(8):
            pil.cyl(pcx - 105 + f * 30, Y - 332, 10, FLOOR + 300, CEIL - 350, n=10)
    for a, b, c, d in ((px(740), px(910), 620.0, 1980.0), (px(740), px(910), -560.0, 460.0)):
        for (u0, u1, v0, v1) in ((a, b, d - 30, d), (a, b, c, c + 30), (a, a + 30, c, d), (b - 30, b, c, d)):
            pil.box(u0, u1, Y - 280, Y - 250, v0, v1)
    pil.box(x0, x1, Y - 270, Y - 240, CEIL - 120, CEIL)                    # cornice
    for n, (a, b, c, d) in NICHES.items():
        xa, xb = px(a), px(b)
        za, zb = NICHE_Z0, NICHE_Z0 + (d - c) * 3.0
        pil.box(xa, xb, Y - 250, Y, zb, CEIL)                              # wall above the niche
    add("shop_pilasters", pil, "plaster")
    add("shop_window_frame", wf, "plaster")

    shelves, leds, frames, cab, tops = Mesh(), Mesh(), Mesh(), Mesh(), Mesh()
    for n, (a, b, c, d) in NICHES.items():
        xa, xb = px(a), px(b)
        zb = NICHE_Z0 + (d - c) * 3.0
        back = Mesh()
        back.quad((xa, Y - 5, NICHE_Z0), (xb, Y - 5, NICHE_Z0), (xb, Y - 5, zb), (xa, Y - 5, zb))
        add(f"shop_{n}", back, n)
        for z in SHELF_Z:
            if z < zb:
                shelves.box(xa, xb, Y - 240, Y - 6, z - 10, z)
                leds.box(xa + 10, xb - 10, Y - 240, Y - 225, z - 16, z - 10)
        frames.box(xa - 30, xa, Y - 260, Y, NICHE_Z0, zb + 30)               # brass niche frame
        frames.box(xb, xb + 30, Y - 260, Y, NICHE_Z0, zb + 30)
        frames.box(xa - 30, xb + 30, Y - 260, Y, zb, zb + 30)
        # the rounded brass-fluted cabinet under the niche, marble top
        ca, cb = xa - 70, xb + 70
        cab.box(ca, cb, Y - 600, Y - 250, FLOOR, NICHE_Z0 - 30)
        for f in range(int((cb - ca) / 34)):
            cab.cyl(ca + 17 + f * 34, Y - 602, 14, FLOOR + 40, NICHE_Z0 - 50, n=10)
        tops.box(ca - 15, cb + 15, Y - 620, Y - 250, NICHE_Z0 - 30, NICHE_Z0)
    add("shop_shelves", shelves, "shelfglass")
    add("shop_leds", leds, "led")
    add("shop_brass", frames, "brass")
    add("shop_cabinets", cab, "brass")
    add("shop_cabinet_tops", tops, "mtop_mat")

    # opal sconces with brass backplates on the centre wall
    sc, bp = Mesh(), Mesh()
    for x in (px(755), px(885)):
        for z0_, z1_ in ((1050.0, 1230.0), (690.0, 870.0)):
            sc.cyl(x, Y - 330, 40, z0_, z1_, n=24)
        bp.box(x - 22, x + 22, Y - 300, Y - 250, 650, 1270)
        bp.cyl(x, Y - 330, 30, 870, 1050, n=16)
    add("shop_sconces", sc, "sconce")
    add("shop_sconce_brass", bp, "brass")
    # ceiling light panels: the room's soft overall light
    lights = Mesh()
    for lx in (-2400.0, -1300.0, -200.0, 900.0):
        for ly in (-700.0, 300.0, 1200.0):
            lights.quad((lx - 300, ly - 300, CEIL - 2), (lx + 300, ly - 300, CEIL - 2), (lx + 300, ly + 300, CEIL - 2), (lx - 300, ly + 300, CEIL - 2))
    add("shop_ceiling_lights", lights, "ceil_light")

    # extra light for a richer scene: sun through the French window, puck spots in the niches, counter downlights
    U = 0.001
    if opt.get("sun", "1") == "1":
        prop("scene.lights.shop_sun.type", "sun")
        prop("scene.lights.shop_sun.dir", -0.35, -0.75, 0.45)              # from outside the window, down into the room
        prop("scene.lights.shop_sun.turbidity", 2.2)
        prop("scene.lights.shop_sun.gain", *([float(opt.get("sun_gain", 0.00004))] * 3))
    k = 0
    for n, (a, b, c, d) in NICHES.items():
        xa, xb = px(a), px(b)
        for z in SHELF_Z + (NICHE_Z0 + (d - c) * 3.0 - 40,):
            for x in np.linspace(xa + 80, xb - 80, 3):
                prop(f"scene.lights.puck{k}.type", "spot")
                prop(f"scene.lights.puck{k}.position", x * U, (Y - 120) * U, (z - 20) * U)
                prop(f"scene.lights.puck{k}.target", x * U, (Y - 120) * U, (z - 400) * U)
                prop(f"scene.lights.puck{k}.coneangle", 40.0)
                prop(f"scene.lights.puck{k}.conedeltaangle", 15.0)
                prop(f"scene.lights.puck{k}.color", 1.0, 0.95, 0.88)
                prop(f"scene.lights.puck{k}.gain", *([float(opt.get("puck", 0.3))] * 3))
                k += 1
    for i, (x, y) in enumerate(((-250.0, 150.0), (300.0, 250.0))):
        prop(f"scene.lights.down{i}.type", "spot")
        prop(f"scene.lights.down{i}.position", x * U, y * U, (CEIL - 10) * U)
        prop(f"scene.lights.down{i}.target", 0.0, 60 * U, 0.0)
        prop(f"scene.lights.down{i}.coneangle", 14.0)
        prop(f"scene.lights.down{i}.conedeltaangle", 6.0)
        prop(f"scene.lights.down{i}.color", 0.96, 0.98, 1.0)
        prop(f"scene.lights.down{i}.gain", *([float(opt.get("down", 3.0))] * 3))


# --- wall5: the straight-on boutique wall (shop/wall5.webp), five lit niches, the centre one behind the bottle --------
W5_MM = 2.4                                    # mm per image px (bottles ~60 px -> ~145 mm)
W5_NICHES = [(55, 271), (356, 562), (652, 885), (975, 1181), (1265, 1479)]   # inner x of each niche (px)
W5_TOP, W5_BOT = 76, 835                       # inner y of the niches (px)
W5_SHELVES = (283, 465, 650)                   # glass shelves (px)
W5_FLOOR_PX = 940                              # the floor line (px)


def build_wall5(define, prop, here, opt):
    """the wall from shop/wall5.webp at 2.4 mm/px: niche back panels lit with the image's crops (the bottles and flowers),
    real glass shelves with LED strips, silver frames, fluted pilasters, white wall, pale floor, ceiling light panels"""
    from PIL import ImageEnhance
    sd = os.path.join(here, "shop")
    im = Image.open(os.path.join(sd, "wall5.webp")).convert("RGB")
    Y = float(opt.get("wall_y", 4500.0))                     # far enough back to show two or three niches at 100 mm
    zfloor = FLOOR
    X = lambda x: (x - 768.5) * W5_MM                          # the centre niche on the bottle
    dz = float(opt.get("wall_dz", 90.0))                        # raise the wall: the middle shelf behind the bottle's shoulder
    Z = lambda y: zfloor + dz + (W5_FLOOR_PX - y) * W5_MM

    def mat(name, typ, **kw):
        prop(f"scene.materials.{name}.type", typ)
        for k, v in kw.items():
            prop(f"scene.materials.{name}.{k}", *v) if isinstance(v, (tuple, list)) else prop(f"scene.materials.{name}.{k}", v)

    def emit(name, src, gain, tint=(1.0, 1.0, 1.0)):
        if isinstance(src, str):
            prop(f"scene.textures.{name}_t.type", "imagemap")
            prop(f"scene.textures.{name}_t.file", os.path.join(sd, src))
            prop(f"scene.textures.{name}_t.gamma", 2.2)
            src = f"{name}_t"
        mat(name, "matte", kd=(0, 0, 0), emission=src)
        prop(f"scene.materials.{name}.emission.gain", *[float(gain) * t for t in tint])

    def add(name, m, material):
        define(name + "_m", np.array(m.p, float), np.array(m.t, np.int64), None, m.uv)
        prop(f"scene.objects.{name}.shape", name + "_m")
        prop(f"scene.objects.{name}.material", material)

    mat("w5wall", "matte", kd=(0.86, 0.86, 0.87))
    mat("w5floor", "glossy2", kd=(0.80, 0.80, 0.80), ks=(0.04, 0.04, 0.04), uroughness=0.08, vroughness=0.08)
    mat("w5silver", "metal2", preset="aluminium", uroughness=0.2, vroughness=0.2)
    mat("shelfglass", "glass", kt=(0.95, 0.97, 0.96), kr=(0.9, 0.9, 0.9), interiorior=1.5)
    emit("led", (0.94, 0.97, 1.0), opt.get("led", 30.0))
    emit("ceil_light", (0.92, 0.95, 1.0), opt.get("ceil", 22.0))
    # the image's five niches repeat along the wall (tiles k = -T..T), so an orbiting camera sees shelves at every angle
    T = int(opt.get("wall_tiles", 2))
    NN = [(a_ + k * 1536, b_ + k * 1536, i) for k in range(-T, T + 1) for i, (a_, b_) in enumerate(W5_NICHES)]
    x0, x1 = X(-T * 1536), X((T + 1) * 1536)
    shell = Mesh()
    shell.quad((x0, -1500, zfloor), (x1, -1500, zfloor), (x1, Y, zfloor), (x0, Y, zfloor))
    shell.quad((x0, -1500, CEIL), (x1, -1500, CEIL), (x1, Y, CEIL), (x0, Y, CEIL))
    shell.quad((x1, -1500, zfloor), (x1, Y, zfloor), (x1, Y, CEIL), (x1, -1500, CEIL))
    shell.quad((x0, Y, zfloor), (x0, -1500, zfloor), (x0, -1500, CEIL), (x0, Y, CEIL))
    shell.quad((x1, -1500, zfloor), (x0, -1500, zfloor), (x0, -1500, CEIL), (x1, -1500, CEIL))
    # back wall face (250 mm proud of the niche backs), with the five niche openings cut out
    D = 250.0
    zt, zb = Z(W5_TOP), Z(W5_BOT)
    xs = [x0] + [v for n in NN for v in (X(n[0]), X(n[1]))] + [x1]
    for i in range(0, len(xs), 2):                                    # the piers between the openings
        shell.box(xs[i], xs[i + 1], Y - D, Y, zfloor, CEIL)
    for a, b, _ in NN:                                                # above and below each opening
        shell.box(X(a), X(b), Y - D, Y, zt, CEIL)
        shell.box(X(a), X(b), Y - D, Y, zfloor, zb)
    add("w5_shell", shell, "w5wall")
    fl = Mesh(); fl.quad((x0, -1500, zfloor + 1), (x1, -1500, zfloor + 1), (x1, Y, zfloor + 1), (x0, Y, zfloor + 1))
    add("w5_floor", fl, "w5floor")
    pil = Mesh()                                                      # fluted pilasters between the niches
    for k in range(len(NN) + 1):
        xl = X(NN[k - 1][1]) if k else x0
        xr = X(NN[k][0]) if k < len(NN) else x1
        cx = (xl + xr) / 2
        for f in range(-2, 3):
            pil.cyl(cx + f * 22, Y - D - 4, 8, zfloor + 120, CEIL - 200, n=10)
    add("w5_pilasters", pil, "w5wall")
    shelves, leds, frames = Mesh(), Mesh(), Mesh()
    for i, (a, b) in enumerate(W5_NICHES):
        ImageEnhance.Color(im.crop((a, W5_TOP, b, W5_BOT))).enhance(0.9).save(os.path.join(sd, f"w5_n{i}.png"))
        emit(f"w5_n{i}", f"w5_n{i}.png", opt.get("niche", 2.2))
    backs = {i: Mesh() for i in range(len(W5_NICHES))}
    for a, b, i in NN:
        backs[i].quad((X(a), Y - 5, zb), (X(b), Y - 5, zb), (X(b), Y - 5, zt), (X(a), Y - 5, zt))
    for i, m_ in backs.items():
        add(f"w5_niche{i}", m_, f"w5_n{i}")
    for a, b, i in NN:
        for yy in W5_SHELVES:
            z = Z(yy)
            shelves.box(X(a), X(b), Y - D, Y - 6, z - 8, z)
            leds.box(X(a) + 8, X(b) - 8, Y - D + 6, Y - D + 20, z - 14, z - 8)
        leds.box(X(a) + 8, X(b) - 8, Y - D + 6, Y - D + 20, zt - 14, zt - 4)       # the top strip
        t = 22.0                                                      # silver frame round the opening
        frames.box(X(a) - t, X(a), Y - D - 6, Y - D + 30, zb - t, zt + t)
        frames.box(X(b), X(b) + t, Y - D - 6, Y - D + 30, zb - t, zt + t)
        frames.box(X(a) - t, X(b) + t, Y - D - 6, Y - D + 30, zt, zt + t)
        frames.box(X(a) - t, X(b) + t, Y - D - 6, Y - D + 30, zb - t, zb)
    add("w5_shelves", shelves, "shelfglass")
    add("w5_leds", leds, "led")
    add("w5_frames", frames, "w5silver")
    # the blossom branch: the photo cut-out (shop/props/branch_card*.png, colour + alpha) on a card facing the camera, just
    # behind the bottle, seen through the glass and liquid. The turntable camera never moves, so the card never shows
    # edge-on; the bottle refracts it truly.
    bc = os.path.join(sd, "props", "branch_card_rgb.png")
    if opt.get("branch", "3d") == "3d":                              # the modelled branch lying on the counter
        import sys as _sys
        _sys.path.insert(0, here)
        import branch3d
        branch3d.build(define, prop, opt)
    elif os.path.exists(bc) and opt.get("branch") == "card":
        for t_, f_ in (("branch_rgb", "branch_card_rgb.png"), ("branch_a", "branch_card_a.png")):
            prop(f"scene.textures.{t_}.type", "imagemap")
            prop(f"scene.textures.{t_}.file", os.path.join(sd, "props", f_))
            prop(f"scene.textures.{t_}.gamma", 2.2 if t_ == "branch_rgb" else 1.0)
        prop("scene.textures.branch_a.channel", "red")
        mat("branch_face", "matte", kd="branch_rgb")
        prop("scene.materials.branch_null.type", "null")
        prop("scene.materials.branch.type", "mix")
        prop("scene.materials.branch.material1", "branch_null")
        prop("scene.materials.branch.material2", "branch_face")
        prop("scene.materials.branch.amount", "branch_a")
        cw = float(opt.get("branch_w", 260.0)); ch = cw * 631.0 / 1404.0
        cx, cy, cz = float(opt.get("branch_x", 0.0)), float(opt.get("branch_y", 90.0)), float(opt.get("branch_z", 95.0))
        roll = math.radians(float(opt.get("branch_roll", -12.0)))   # tilt in the picture plane: a diagonal branch
        tilt = math.radians(float(opt.get("branch_tilt", 0.0)))     # lean back from the counter: 90 = lying flat
        cr, sr = math.cos(roll), math.sin(roll)
        corners = [(-cw / 2, -ch / 2), (cw / 2, -ch / 2), (cw / 2, ch / 2), (-cw / 2, ch / 2)]
        uw = [(u * cr - w * sr, u * sr + w * cr) for u, w in corners]       # rolled, in the card plane
        wmin = min(w for _, w in uw)
        # lean back about the card's lowest point, which rests on the counter (cz is ignored once tilted)
        if tilt:
            pts = [(cx + u, cy + (w - wmin) * math.sin(tilt), 0.5 + (w - wmin) * math.cos(tilt)) for u, w in uw]
        else:
            pts = [(cx + u, cy, cz + w) for u, w in uw]
        card = Mesh(); card.quad(*pts, uv=((0, 1), (1, 1), (1, 0), (0, 0)))
        add("w5_branch", card, "branch")
    lights = Mesh()
    for lx in np.arange(x0 + 600, x1 - 300, 1200.0):
        for ly in (-700.0, 300.0, 1100.0):
            lights.quad((lx - 300, ly - 300, CEIL - 2), (lx + 300, ly - 300, CEIL - 2), (lx + 300, ly + 300, CEIL - 2), (lx - 300, ly + 300, CEIL - 2))
    add("w5_ceiling_lights", lights, "ceil_light")
