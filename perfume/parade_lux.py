"""LuxCoreRender scene for the keel Parade bottle, built straight from the keel meshes (mesh/*.npz, exact B-rep
normals), for the thick-glass look Cycles struggles with.

    python parade_lux.py view=front|three_quarter|top|neck [res=WxH] [time=S] [out=x.png]

Thick glass, done the LuxCore way:
  - nested dielectrics by volume priority: the glass is a closed solid (cavity faces kept, glass_full.npz), the
    liquid a closed solid pushed 0.03 mm into it; the juice volume outranks the glass volume, so at the wet wall the
    refraction uses juice | glass (1.36 / 1.52) and inside the overlap there is no spurious interface
  - Beer-Lambert absorption in the juice (per metre: blue 20, green 5.6, red 0, as measured off the photos)
  - dispersion on the glass (Cauchy B), so edges fringe like real flint glass
  - caustics: path tracing with hybrid back/forward light tracing, so light focused through the glass onto the floor
    and into the base converges
Polished-aluminium collar and pump (measured n/k, soft roughness), black lacquer cap, printed paper label (UV from
the label plane), a self-lit light-grey sweep, softbox strips as emissive quads, the Poly Haven studio HDRI.
"""
import json
import math
import os
import sys
import time

import numpy as np
import pyluxcore
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OPT = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
VIEW = OPT.get("view", "front")
RES = [int(v) for v in OPT.get("res", "720x900").split("x")]
HALT = float(OPT.get("time", 120))
OUT = os.path.join(HERE, OPT.get("out", f"lux_{VIEW}.png"))
MODE = OPT.get("mode", "full")      # full | plate (the studio without the bottle) | mask (bottle alpha, sweep hidden)
U = 0.001                                         # keel works in mm; LuxCore volumes want metres

pyluxcore.Init(lambda msg: None)
info = json.load(open(os.path.join(HERE, "parade_parts.json")))
scene = pyluxcore.Scene()
P = pyluxcore.Properties()


def plain(v):
    """LuxCore properties want plain Python values (numpy scalars raise std::bad_cast)"""
    if isinstance(v, (str, bool)):
        return v
    return int(v) if isinstance(v, (int, np.integer)) else float(v)


def prop(key, *vals):
    vals = [plain(v) for v in vals]
    P.Set(pyluxcore.Property(key, vals if len(vals) > 1 else vals[0]))


def load(name, crease=8.0):
    """mesh with the B-rep's exact normals, split along sharp edges: LuxCore takes one normal per vertex, and the
    tessellator shares a vertex between two faces meeting at an edge (the cap's flats), which would average them"""
    m = np.load(os.path.join(HERE, OPT.get("meshdir", "mesh"), f"{name}.npz"))
    pts, vn, tris = m["points"].astype(np.float64), m["normals"].astype(np.float64), m["tris"].astype(np.int64)
    fn = np.cross(pts[tris[:, 1]] - pts[tris[:, 0]], pts[tris[:, 2]] - pts[tris[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    sharp = np.einsum("ncj,nj->nc", vn[tris], fn) < math.cos(math.radians(crease))
    ti, ci = np.nonzero(sharp)                                  # corners across a crease get their own vertex
    new = len(pts) + np.arange(len(ti))
    pts = np.vstack([pts, pts[tris[ti, ci]]])
    vn = np.vstack([vn, fn[ti]])
    tris = tris.copy()
    tris[ti, ci] = new
    return pts, vn, tris


# spin=<deg>: turntable. The bottle turns about its vertical axis, the camera, lights and set stay put (the same view as
# moving the camera by -spin, with the shop behind the bottle in every frame)
SPIN = math.radians(float(OPT.get("spin", 0.0)))
BOTTLE_SHAPES = {"glass_m", "juice_m", "label_m"} | {f"{n}_m" for n in ("collar", "pump", "cap", "dip_tube", "outlet", "emblem_cap", "emblem_act")}


MESHES = {}                        # every mesh as defined (mm), for export=<file> (the Blender layout handoff)


def define(name, pts, tris, nrm=None, uv=None):
    if SPIN and name in BOTTLE_SHAPES:
        c_, s_ = math.cos(SPIN), math.sin(SPIN)
        rot = np.array([[c_, -s_, 0.0], [s_, c_, 0.0], [0.0, 0.0, 1.0]])
        pts = np.asarray(pts) @ rot.T
        nrm = None if nrm is None else np.asarray(nrm) @ rot.T
    if OPT.get("export"):
        MESHES[name] = (np.asarray(pts, float), np.asarray(tris, np.int64), None if uv is None else np.asarray(uv, float))
    scene.DefineMesh(name, [tuple(p) for p in (pts * U)], [tuple(t) for t in tris],
                     None if nrm is None else [tuple(n) for n in nrm], None if uv is None else [tuple(t) for t in uv], None, None)


# --- volumes and materials -------------------------------------------------------------------------------------
prop("scene.volumes.glassvol.type", "clear")
prop("scene.volumes.glassvol.ior", 1.52)
prop("scene.volumes.glassvol.absorption", 0.02, 0.008, 0.012)        # faint green of flint glass, per metre
prop("scene.volumes.glassvol.priority", 1)
prop("scene.volumes.juicevol.type", "clear")
prop("scene.volumes.juicevol.ior", 1.36)
# calibrated on ref_front: the gold below the label is (238, 203, 131) on a 235 backdrop, through 38.8 mm of liquid
# (the modelled path at the front centre) -> Beer-Lambert sigma = -ln(T) / L = (0, 8.3, 33) per metre
GOLD = float(OPT.get("gold", 1.0))     # the photo calibration (x1.5 turned the long top/neck paths orange)
# pale champagne gold: green absorbed at ~0.2 x the blue rate (more reads amber-orange, as the last render did)
prop("scene.volumes.juicevol.absorption", 0.4 * GOLD, 10.5 * GOLD, 40.0 * GOLD)   # front calibration again: the two-view fit
#   (6.3, 32) washed the front out and hid the inner curves (iteration-4 feedback); the top view's long path pays
prop("scene.volumes.juicevol.priority", 2)
prop("scene.volumes.plastic.type", "clear")
prop("scene.volumes.plastic.ior", 1.40)                             # close to the juice: the tube nearly vanishes
prop("scene.volumes.plastic.priority", 3)

prop("scene.materials.glass.type", "glass")
prop("scene.materials.glass.kr", 1.0, 1.0, 1.0)
prop("scene.materials.glass.kt", 1.0, 1.0, 1.0)
prop("scene.materials.glass.cauchyb", float(OPT.get("dispersion", 0.002)))   # stage B: 0.0042 vs 0 barely differ; subtle
prop("scene.materials.glass.volume.interior", "glassvol")
prop("scene.materials.juice.type", "glass")
prop("scene.materials.juice.kr", 1.0, 1.0, 1.0)
prop("scene.materials.juice.kt", 1.0, 1.0, 1.0)
prop("scene.materials.juice.volume.interior", "juicevol")   # a volume named like its material breaks parsing
prop("scene.materials.tube.type", "glass")                            # smooth: roughness drew a white line
prop("scene.materials.tube.kr", 1.0, 1.0, 1.0)
prop("scene.materials.tube.kt", 1.0, 1.0, 1.0)
prop("scene.materials.tube.volume.interior", "plastic")
# the sprinkler: polished aluminium (measured n/k), soft wide highlights rather than a perfect mirror
prop("scene.materials.alu.type", "metal2")
prop("scene.materials.alu.preset", "aluminium")
prop("scene.materials.alu.uroughness", float(OPT.get("alu_rough", 0.07)))   # satin aluminium (iteration 7: 0.015 read as chrome)   # polished, soft-edged highlights
prop("scene.materials.alu.vroughness", float(OPT.get("alu_rough", 0.07)))
prop("scene.materials.lacquer.type", "glossy2")
prop("scene.materials.lacquer.kd", 0.002, 0.002, 0.0025)
prop("scene.materials.lacquer.ks", *([float(OPT.get("lacquer_ks", 0.045))] * 3))
prop("scene.materials.lacquer.uroughness", 0.012)
prop("scene.materials.lacquer.vroughness", 0.012)
# the cap emblem's rims (iteration 5): black lacquer like the cap, but its specular level set apart (emblem_ks) so the
# fine rims can catch the studio as the bright double outlines of ref_top
prop("scene.materials.rim.type", "glossy2")
prop("scene.materials.rim.kd", 0.002, 0.002, 0.0025)
prop("scene.materials.rim.ks", *([float(OPT.get("emblem_ks", 0.045))] * 3))
prop("scene.materials.rim.uroughness", float(OPT.get("emblem_rough", 0.012)))
prop("scene.materials.rim.vroughness", float(OPT.get("emblem_rough", 0.012)))
if "rim_emit" in OPT:                                                  # diagnostic: make the rims glow
    prop("scene.materials.rim.emission", *([float(OPT["rim_emit"])] * 3))
# label: paper colour with the print, mapped by UV from the label plane
lbl = info["label"]
art = Image.open(os.path.join(HERE, "label_print.png")).convert("RGBA")
paper = Image.new("RGBA", art.size, (246, 246, 246, 255))           # neutral white (a cream base read warm in iteration 4)
Image.alpha_composite(paper, art).convert("RGB").save(os.path.join(HERE, "label_rgb.png"))
prop("scene.textures.labelimg.type", "imagemap")
prop("scene.textures.labelimg.file", os.path.join(HERE, "label_rgb.png"))
prop("scene.textures.labelimg.gamma", 2.2)
if "texfilter" in OPT:
    prop("scene.textures.labelimg.filter", OPT["texfilter"])
    prop("scene.textures.paper_relief.filter", OPT["texfilter"])
prop("scene.textures.paper_relief.type", "imagemap")               # woven knurl + embossed border (make_label.py)
prop("scene.textures.paper_relief.file", os.path.join(HERE, "label_bump.png"))
prop("scene.textures.paper_relief.gamma", 1.0)
prop("scene.textures.paper_bump.type", "scale")
prop("scene.textures.paper_bump.texture1", "paper_relief")
prop("scene.textures.paper_bump.texture2", float(OPT.get("paper_bump", 0.00024)))   # metres of relief
prop("scene.materials.paper.type", "matte")
prop("scene.materials.paper.kd", "labelimg")
prop("scene.materials.paper.bumptex", "paper_bump")
# sweep: mostly self-lit, so floor and wall read as one even grey; its diffuse part keeps shadow and caustics
prop("scene.materials.sweep.type", "matte")
prop("scene.materials.sweep.kd", *([float(OPT.get("sweep_kd", 0.5))] * 3))   # mostly diffuse: the key casts a shadow
prop("scene.materials.sweep.emission", 1.0, 1.0, 0.99)
prop("scene.materials.sweep.emission.gain", *([float(OPT.get("glow", 0.15))] * 3))
prop("scene.materials.sweep.emission.importance", 0.05)              # a huge dim emitter: don't waste light samples on it

if OPT.get("clay", "0") == "1":                                      # neutral geometry check: all opaque matte grey
    for m in ("glass", "juice", "tube", "alu", "lacquer", "paper"):
        for k in [k for k in P.GetAllNames() if k.startswith(f"scene.materials.{m}.")]:
            P.Delete(k)
        prop(f"scene.materials.{m}.type", "matte")
        prop(f"scene.materials.{m}.kd", 0.35, 0.35, 0.35)          # 0.55 washed the faces out

# --- the bottle ----------------------------------------------------------------------------------------------------
BOTTLE = MODE != "plate"
GLASS = BOTTLE and OPT.get("noglass", "0") != "1"                    # noglass=1: diagnose what the glass hides
SHOW_GLASS = GLASS and OPT.get("liquidonly", "0") != "1"             # liquidonly=1: the juice volume alone
SHOW_JUICE = GLASS and OPT.get("noliquid", "0") != "1"               # noliquid=1: glass alone (empty bottle)
pts, nrm, tris = load("glass_full")
define("glass_m", pts, tris, nrm)
if SHOW_GLASS:
    prop("scene.objects.glass.shape", "glass_m")
    prop("scene.objects.glass.material", "glass")
pts, nrm, tris = load("liquid")
define("juice_m", pts + nrm * 0.03, tris, nrm)                       # 0.03 mm into the glass: priority settles it
if SHOW_JUICE:
    prop("scene.objects.juice.shape", "juice_m")
    prop("scene.objects.juice.material", "juice")
prop("scene.materials.insert.type", "glossy2")                     # the outlet's pale satin insert (ref_neck)
prop("scene.materials.insert.kd", 0.72, 0.72, 0.72)
prop("scene.materials.insert.ks", 0.04, 0.04, 0.04)
prop("scene.materials.insert.uroughness", 0.25)
prop("scene.materials.insert.vroughness", 0.25)
for name, mat in (("collar", "alu"), ("pump", "alu"), ("cap", "lacquer"), ("dip_tube", "tube"), ("outlet", "insert"),
                  ("emblem_cap", "rim"), ("emblem_act", "alu")):
    if not os.path.exists(os.path.join(HERE, OPT.get("meshdir", "mesh"), f"{name}.npz")):
        continue
    if not BOTTLE or (VIEW == "neck" and name in ("cap", "emblem_cap")) or (name == "dip_tube" and OPT.get("notube", "0") == "1"):
        continue                                                     # the close-up photo has the cap off
    pts, nrm, tris = load(name)
    define(f"{name}_m", pts, tris, nrm)
    prop(f"scene.objects.{name}.shape", f"{name}_m")
    prop(f"scene.objects.{name}.material", mat)
if OPT.get("cut") == "1":
    # cutaway (cut_meshes.py, meshdir=mesh_cut): the cut faces of every part painted in a gloss red, a hair in front
    # of the section so the glass behind keeps its closed solid
    prop("scene.materials.cutpaint.type", "glossy2")
    prop("scene.materials.cutpaint.kd", 0.55, 0.035, 0.03)
    prop("scene.materials.cutpaint.ks", 0.03, 0.03, 0.03)
    prop("scene.materials.cutpaint.uroughness", 0.15); prop("scene.materials.cutpaint.vroughness", 0.15)
    for name in ("glass_full", "collar", "pump", "cap", "dip_tube", "emblem_cap", "emblem_act"):
        f = os.path.join(HERE, OPT.get("meshdir", "mesh"), f"{name}_capface.npz")
        if not os.path.exists(f) or (name != "glass_full" and OPT.get("redall", "0") != "1"):
            continue
        m = np.load(f)
        define(f"{name}_capface_m", m["points"] + np.array([0, -0.02, 0]), m["tris"], m["normals"])
        prop(f"scene.objects.{name}_capface.shape", f"{name}_capface_m")
        prop(f"scene.objects.{name}_capface.material", "cutpaint")
pts, nrm, tris = load("label")
uv = np.stack([pts[:, 0] / lbl["w"] + 0.5, 1 - (pts[:, 2] - lbl["z0"]) / lbl["h"]], axis=1)   # LuxCore's v runs down
define("label_m", pts, tris, nrm, uv)
if BOTTLE and OPT.get("label", "1") == "1" and OPT.get("cut") != "1":                         # label=0: diagnose the glass and liquid alone
    prop("scene.objects.label.shape", "label_m")
    prop("scene.objects.label.material", "paper")

# --- studio --------------------------------------------------------------------------------------------------------
prof = [(-3000.0, -0.2), (150.0, -0.2)] + [(150 + 300 * math.sin(t * math.pi / 24), 300 - 300 * math.cos(t * math.pi / 24) - 0.2)
                                             for t in range(1, 13)] + [(450.0, 3000.0)]
sv, st = [], []
for i, (y, z) in enumerate(prof):
    sv += [(-3000.0, y, z), (3000.0, y, z)]
    if i:
        a = 2 * (i - 1)
        st += [(a, a + 1, a + 3), (a, a + 3, a + 2)]
sv, st = np.array(sv), np.array(st)
fn = np.cross(sv[st[:, 1]] - sv[st[:, 0]], sv[st[:, 2]] - sv[st[:, 0]])
flip = (fn[:, 2] - fn[:, 1]) < 0                    # emission is one-sided: up on the floor, toward the bottle on the wall
st[flip] = st[flip][:, ::-1]
define("sweep_m", sv, st)
prop("scene.objects.sweep.shape", "sweep_m")
prop("scene.objects.sweep.material", "sweep")
if MODE == "mask":
    prop("scene.objects.sweep.camerainvisible", 1)                  # alpha then marks the bottle only


# cameras fitted to the photos by silhouette overlap (fit_poses.py -> poses.json): azimuth, elevation, distance, target
_P = json.load(open(os.path.join(HERE, "poses.json")))


def _cam(p):
    a, e = math.radians(p["az"]), math.radians(p["el"])
    return ((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)), tuple(p["target"]), p["dist"])


VIEWS = {v: _cam(p) for v, p in _P.items()}
if "az" in OPT:                                                       # diagnostic: override the azimuth of this view
    _P[VIEW] = dict(_P[VIEW], az=float(OPT["az"]))
    VIEWS[VIEW] = _cam(_P[VIEW])
if VIEW == "three_quarter" and "el" not in OPT:                     # iteration 5b: the reviewer asked for a higher camera
    OPT["el"] = "25"
if "el" in OPT:                                                       # override the elevation (iteration 5: 3/4 higher)
    _P[VIEW] = dict(_P[VIEW], el=float(OPT["el"]))
    VIEWS[VIEW] = _cam(_P[VIEW])
LENS = float(OPT.get("lens", {"front": 200.0}.get(VIEW, 100.0)))   # front: 200 mm (iteration 5b: the base read like ref_front only with the longer lens)   # focal length, mm; the distance scales with it so the bottle keeps its size
# the studio (lights, flags, backdrop card) is laid out for the front camera and turns with the camera about the
# vertical, as a photographer moves the set: fixed, a flag ended up beside the lens in the three-quarter view
_d = VIEWS[VIEW][0]
_turn = math.atan2(_d[1], _d[0]) + math.pi / 2 if math.hypot(_d[0], _d[1]) > 1e-3 else 0.0
if OPT.get("turn", "1") == "0":
    _turn = 0.0
_R = np.array([[math.cos(_turn), -math.sin(_turn), 0], [math.sin(_turn), math.cos(_turn), 0], [0, 0, 1]])


def turn(p):
    return tuple(_R @ np.array(p, float))


OFF = set(OPT.get("off", "").split(","))                             # diagnostic: lights / flags to leave out
CARD_TOP = float(OPT.get("card_top", 115.0))                         # top of the backlit card (see below)


def softbox(name, centre, size, gain, aim=(0, 0, 60)):
    """an emissive rectangle facing `aim` (LuxCore area light); placed for the front camera, turned with the view"""
    if name in OFF:
        return
    c, a = np.array(turn(centre), float), np.array(turn(aim), float)
    n = (a - c) / np.linalg.norm(a - c)
    up = np.array([0, 0, 1.0]) if abs(n[2]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(up, n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    w, h = size
    q = np.array([c - u * w / 2 - v * h / 2, c + u * w / 2 - v * h / 2, c + u * w / 2 + v * h / 2, c - u * w / 2 + v * h / 2])
    tri = np.array([(0, 1, 2), (0, 2, 3)])
    if np.dot(np.cross(q[1] - q[0], q[2] - q[0]), n) < 0:             # emission is one-sided: face the bottle
        tri = tri[:, ::-1]
    define(f"{name}_m", q, tri)
    prop(f"scene.materials.{name}_e.type", "matte")
    prop(f"scene.materials.{name}_e.kd", 0.0, 0.0, 0.0)
    prop(f"scene.materials.{name}_e.emission", 1.0, 1.0, 1.0)            # neutral: warm sources tinted the paper
    prop(f"scene.materials.{name}_e.emission.gain", gain, gain, gain)
    prop(f"scene.objects.{name}.shape", f"{name}_m")
    prop(f"scene.objects.{name}.material", f"{name}_e")
    if MODE == "mask":
        prop(f"scene.objects.{name}.camerainvisible", 1)
    # (no camerainvisible: in this LuxCore it also hides the object from mirror paths, so the cap lost its bands)


def flag(name, centre, size, aim=(0, 0, 60)):
    """a black card beside the set: the lacquer and the glass edges mirror darkness instead of the glowing sweep"""
    if OPT.get("noflags", "0") == "1" or name in OFF:              # diagnostic: no black cards
        return
    c, a = np.array(turn(centre), float), np.array(turn(aim), float)
    n = (a - c) / np.linalg.norm(a - c)
    u = np.cross(np.array([0, 0, 1.0]), n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    w, h = size
    q = np.array([c - u * w / 2 - v * h / 2, c + u * w / 2 - v * h / 2, c + u * w / 2 + v * h / 2, c - u * w / 2 + v * h / 2])
    define(f"{name}_m", q, np.array([(0, 1, 2), (0, 2, 3)]))
    prop(f"scene.objects.{name}.shape", f"{name}_m")
    prop(f"scene.objects.{name}.material", "flagblack")
    if MODE == "mask":
        prop(f"scene.objects.{name}.camerainvisible", 1)             # the mask is the bottle only


prop("scene.materials.flagblack.type", "matte")
prop("scene.materials.flagblack.kd", 0.0, 0.0, 0.0)
for sx in (-1, 1):
    flag(f"flag_front_{sx}", (sx * 260, -330, 140), (220, 520))          # beside the camera, outside the strips
    flag(f"flag_side_{sx}", (sx * 420, 40, 140), (300, 520))           # far enough out to stay out of the 3/4 frame
flag("flag_back_cam", (0, -700 * max(1.0, LENS / 100.0) - (LENS - 100) * 2.0, 160), (700, 520))   # behind the camera (moves back with a longer lens)
# above the card (cap top, actuator top); the low front camera would see it, so there it starts above the frame
FLAG_Z0 = {"front": 175.0}.get(VIEW, CARD_TOP)
flag("flag_over", (0, 150, FLAG_Z0 + 150), (600, 300), aim=(0, -400, FLAG_Z0 + 150))


G = float(OPT.get("lights", 1.0))
# the white backdrop seen through the glass: an even card behind the bottle, so refraction never shows the sweep's
# floor/wall horizon inside the liquid
prop("scene.materials.card.type", "matte")
prop("scene.materials.card.kd", 0.0, 0.0, 0.0)
prop("scene.materials.card.emission", 1.0, 1.0, 0.99)
prop("scene.materials.card.emission.gain", *([float(OPT.get("card", 0.9))] * 3))
# the card stops at z 115: the cap's top face mirrors the scene behind and above it (from the 3/4 camera a ray off the
# top lands at z ~165 on this plane); a black flag takes over above, so the polished top reads dark (iteration 4)
cq = np.array([turn(p) for p in ((-260.0, 140.0, -0.2), (260.0, 140.0, -0.2), (260.0, 140.0, CARD_TOP), (-260.0, 140.0, CARD_TOP))])
define("card_m", cq, np.array([(0, 1, 2), (0, 2, 3)]))               # normal -Y, toward the bottle (emission is one-sided)
if "card" not in OFF:
    prop("scene.objects.card.shape", "card_m")
    prop("scene.objects.card.material", "card")
if MODE == "mask":
    prop("scene.objects.card.camerainvisible", 1)
# directly visible behind the bottle too: the clean-plate pass normalises whatever backdrop the camera sees
# radiances relative to the sweep's 0.6 glow (LuxCore gains are radiance, not Cycles watts)
# the cap's flat facets are mirrors: one facet right of centre mirrors this strip as one bright band; nothing mirrors
# into the left facets, which stay black, as in the front photo
softbox("strip_r", (260, -150, 140), (60, 420), float(OPT.get("strip", 16.0)) * G)  # (12-sided cap, a flat facing the
#                                       camera: the front-right facet, normal at -60 deg, mirrors azimuth -30 deg)
softbox("back", (0, 260, 120), (260, 300), 0.8 * G)                # glows through the juice; brighter clips the gold to white
# the dominant light: a big key from camera right, a little in front and above -> the photos' soft shadow to the left
softbox("key", (420, -120, 260), (420, 420), float(OPT.get("key", 5.0)) * G)
#                                                                     (kept out of the three-quarter frame)
# broad frontal fill, kept LOW: it lights the label but sits below what the cap's vertical facets mirror (at the
# fill's old height the black cap turned grey)
softbox("fill", (0, -600, 25), (520, 110), float(OPT.get("fill", 2.2)) * G, aim=(0, 0, 50))
# and a broad fill high in front (about 55 deg up): it whitens the label, while the cap's vertical facets, which mirror
# only what sits near the camera's own elevation, never show it
# view-specific (documented): the neck close-up dims it, else the polished actuator top mirrors it as a white disc
FILL_HI = {"neck": 1.5, "three_quarter": 6.0}.get(VIEW, 2.5)   # 3/4: the label faces away from the key
softbox("fill_hi", (0, -260, 420), (420, 300), float(OPT.get("fill_hi", FILL_HI)) * G, aim=(0, 0, 50))
# grazing light for the paper: low, far to the camera's left, skimming the label's face so grain and the embossed
# frame cast tiny shadows (the frontal fill alone lit them flat)
softbox("graze", (-330, -90, 75), (60, 200), float(OPT.get("graze", 6.0)) * G, aim=(0, -24, 55))
# the cap emblem from above (iteration 5): the groove walls slope 45 deg, so a straight-down view reflects off them
# horizontally; a ring of eight strips round the cap at its own height (EMBLEM_EL deg above it, top view only,
# documented) is what both walls of every stroke mirror, drawing the motif as two bright contours (ref_top). The
# iteration-4 strips sat 20 deg below the cap top, which a 45 deg wall never sees.
if VIEW == "top":
    el = math.radians(float(OPT.get("emblem_el", 8.0)))
    rad = float(OPT.get("emblem_r", 244.0))
    ne = int(OPT.get("emblem_n", 16))                  # strips in the ring: every stroke direction sees one
    for k in range(ne):
        a = math.radians(180.0 / ne + 360.0 * k / ne)
        softbox(f"emblem_{k}", (rad * math.cos(a), rad * math.sin(a), 114.6 + rad * math.tan(el)), (2 * math.pi * rad / ne * 1.05, 40),
                float(OPT.get("emblem_light", 40.0)) * G, aim=(0, 0, 114.6))
# dark edges for the glass walls: narrow black flags just outside the frame on both sides; the thick walls refract
# them as the dark lines that outline the gold in ref_front (the even backlight alone left the inner curves invisible)
for sx in (-1, 1):
    flag(f"flag_near_{sx}", (sx * 150, 50, 110), (70, 320), aim=(0, 0, 60))
# metal: one dark card and one light card at the side, so the polished sleeve shows light/dark bands (ref_neck)
if VIEW == "neck":
    # iteration 5: the label read grey in the neck view (fill_hi is kept low there for the actuator top); a light low
    # beside the camera for the label alone
    softbox("label_neck", (0, -350, 0), (260, 160), float(OPT.get("label_neck", 22.0)) * G, aim=(0, -24, 45))
    flag("flag_metal", (-150, -40, 110), (90, 200), aim=(0, 0, 95))
    softbox("strip_metal", (150, -80, 110), (30, 200), float(OPT.get("strip_metal", 6.0)) * G, aim=(0, 0, 95))
prop("scene.lights.studio.type", "infinite")
prop("scene.lights.studio.file", os.path.join(HERE, "studio_small_08_2k.hdr"))
HDRI_GAIN = {"top": 0.1}.get(VIEW, 0.05)          # top: 0.5 greyed the black lacquer; the emblem ring lights it now          # top view: a bright surround for the emblem's walls to mirror
prop("scene.lights.studio.gain", *([float(OPT.get("hdri", HDRI_GAIN))] * 3))   # dim elsewhere: the cap's facets mirror it
# the HDRI turns with the studio too: fixed, its bright softboxes faced the label head-on in the three-quarter view
# (10x the label's front-view light, which washed the print and the embossing out)
_c, _s = math.cos(_turn), math.sin(_turn)
prop("scene.lights.studio.transformation", _c, _s, 0.0, 0.0, -_s, _c, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)

d, tgt, dist = VIEWS[VIEW]
d = np.array(d, float) / np.linalg.norm(d)
eye = np.array(tgt, float) + d * dist * LENS / 100.0
prop("scene.camera.type", "perspective")
prop("scene.camera.lookat.orig", *(eye * U))
prop("scene.camera.lookat.target", *(np.array(tgt, float) * U))
prop("scene.camera.up", 0.0, 0.0, 1.0)
prop("scene.camera.fieldofview", math.degrees(2 * math.atan(18 / LENS)))   # 100 mm lens, 36 mm sensor; LuxCore's FOV spans the long side
# --- shop set (shop=1): the generated boutique image as a 3D set ----------------------------------------------------
SHOP = OPT.get("shop", "0") == "1"
if SHOP:
    # out: the studio sweep, the black cards and the studio softboxes (the key stays for the caustics, the two front
    # fills for the label and the glass: without them the bottle read grey against the lit shop)
    for k in list(P.GetAllNames()):
        obj = k.split(".")[2] if k.startswith("scene.objects.") else None
        if obj and (obj in ("sweep", "card") or obj.startswith("flag") or (obj not in ("key", "fill", "fill_hi", "graze") and f"scene.materials.{obj}_e.type" in P.GetAllNames())):
            P.Delete(k)
    SD = os.path.join(HERE, "shop")
    # counter: a marble slab, top at z = 0 (the bottle stands on it), 1.6 m wide, front edge 90 mm in front of the bottle
    cw, cd, ch, cy0 = 1600.0, float(OPT.get("counter_d", 300.0)), 40.0, -90.0
    def quad(name, q, uv, mat):
        define(name + "_m", np.array(q, float), np.array([(0, 1, 2), (0, 2, 3)]), None, uv)
        prop(f"scene.objects.{name}.shape", name + "_m"); prop(f"scene.objects.{name}.material", mat)
    for tname, fname in (("mtop", "marble_top.png"), ("mfront", "marble_front.png")):
        prop(f"scene.textures.{tname}.type", "imagemap"); prop(f"scene.textures.{tname}.file", os.path.join(SD, fname))
        prop(f"scene.textures.{tname}.gamma", 2.2)
        prop(f"scene.materials.{tname}_mat.type", "glossy2"); prop(f"scene.materials.{tname}_mat.kd", tname)
        prop(f"scene.materials.{tname}_mat.ks", 0.05, 0.05, 0.05)
        prop(f"scene.materials.{tname}_mat.uroughness", 0.03); prop(f"scene.materials.{tname}_mat.vroughness", 0.03)
    quad("counter_top", [(-cw / 2, cy0, -0.2), (cw / 2, cy0, -0.2), (cw / 2, cy0 + cd, -0.2), (-cw / 2, cy0 + cd, -0.2)],
         [(0, 1), (1, 1), (1, 0), (0, 0)], "mtop_mat")
    quad("counter_front", [(-cw / 2, cy0, -ch), (cw / 2, cy0, -ch), (cw / 2, cy0, -0.2), (-cw / 2, cy0, -0.2)],
         [(0, 1), (1, 1), (1, 0), (0, 0)], "mfront_mat")
    # the boutique as a mesh set (walls, pilasters, niches, mirror, window, cabinets, blossom branch)
    sys.path.insert(0, HERE)
    import shop_set
    shop_set.build(define, prop, HERE, OPT)
    # the label read grey: in the studio the white sweep bounces light onto it, the shop has no sweep. A soft light
    # aimed at the label, in front of the bottle (turns with the view), unseen by the camera
    softbox("label_shop", (0, -330, 70), (300, 220), float(OPT.get("label_shop", 14.0)) * G, aim=(0, -24, 50))
    for f in ("fill", "fill_hi", "label_shop"):  # long lenses put the camera behind the fills: light the bottle, never seen
        if f"scene.objects.{f}.shape" in P.GetAllNames():
            prop(f"scene.objects.{f}.camerainvisible", 1)
    # depth of field like a product photo: the shop softens behind the bottle
    prop("scene.camera.lensradius", float(OPT.get("aperture", 0.004)))
    prop("scene.camera.focaldistance", float(np.linalg.norm(eye - np.array(tgt, float)) * U))
    prop("scene.lights.studio.gain", *([float(OPT.get("hdri", 0.02))] * 3))

if OPT.get("layout"):              # the layout edited in Blender (blend/make_blend.py -> read_layout.py)
    LAY = json.load(open(OPT["layout"]))
    names = set(P.GetAllNames())
    moved = 0
    for o, m in LAY["objects"].items():
        if f"scene.objects.{o}.shape" not in names:
            print("layout: no object", o, "in the scene (new in Blender?), skipped", flush=True)
            continue
        if any(abs(a - b) > 1e-9 for a, b in zip(m, (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))):
            prop(f"scene.objects.{o}.transformation", *[float(v) for v in m]); moved += 1
    c = LAY["camera"]
    prop("scene.camera.lookat.orig", *[v * U for v in c["orig"]])
    prop("scene.camera.lookat.target", *[v * U for v in c["target"]])
    prop("scene.camera.up", *c["up"])
    prop("scene.camera.fieldofview", math.degrees(2 * math.atan(18 / c["lens"])))
    if "scene.camera.focaldistance" in names:
        prop("scene.camera.focaldistance", c["focus_mm"] * U)
    print("layout:", moved, "objects moved, camera from", OPT["layout"], flush=True)

if OPT.get("export"):              # hand the scene to Blender (make_blend.py) instead of rendering
    import pickle
    names = set(P.GetAllNames())
    def val(k):
        return list(P.Get(k).Get()) if k in names else None
    objs = {}
    for k in names:
        if k.startswith("scene.objects.") and k.endswith(".shape"):
            o = k.split(".")[2]
            m = P.Get(f"scene.objects.{o}.material").GetString() if f"scene.objects.{o}.material" in names else ""
            objs[o] = {"shape": P.Get(k).GetString(), "material": m, "camerainvisible": f"scene.objects.{o}.camerainvisible" in names}
    mats = {}
    for k in names:
        if k.startswith("scene.materials."):
            m, field = k.split(".")[2], ".".join(k.split(".")[3:])
            mats.setdefault(m, {})[field] = [str(x) for x in P.Get(k).Get()]
    texs = {}
    for k in names:
        if k.startswith("scene.textures.") and k.endswith(".file"):
            texs[k.split(".")[2]] = P.Get(k).GetString()
    cam = {"orig": [x / U for x in val("scene.camera.lookat.orig")], "target": [x / U for x in val("scene.camera.lookat.target")],
           "up": val("scene.camera.up"), "fov": val("scene.camera.fieldofview")[0], "lens": LENS,
           "res": [int(v) for v in OPT.get("res", "720x900").split("x")]}
    pickle.dump({"meshes": MESHES, "objects": objs, "materials": mats, "textures": texs, "camera": cam,
                 "opt": OPT}, open(OPT["export"], "wb"))
    print("exported", len(objs), "objects to", OPT["export"], flush=True)
    os._exit(0)

groups = {}                        # parse entity by entity (each volume, material, object ...) so a bad one is named
for k in P.GetAllNames():
    parts = k.split(".")
    key = "scene.camera" if k.startswith("scene.camera.") else ".".join(parts[:3])   # a camera parses in one go
    groups.setdefault(key, []).append(k)
for g, keys in groups.items():
    q = pyluxcore.Properties()
    for k in keys:
        q.Set(P.Get(k))
    try:
        scene.Parse(q)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"LuxCore rejected {g}: {e}")

# --- render --------------------------------------------------------------------------------------------------------
C = pyluxcore.Properties()
for k, v in (("renderengine.type", OPT.get("engine", "PATHOCL")), ("sampler.type", "SOBOL"),
             ("path.hybridbackforward.enable", 1), ("path.hybridbackforward.partition", 0.8),
             ("path.pathdepth.total", 48), ("path.pathdepth.diffuse", 8), ("path.pathdepth.glossy", 24),
             ("path.pathdepth.specular", 48), ("path.clamping.variance.maxvalue", 0.0),
             ("opencl.cpu.use", 0), ("opencl.gpu.use", 1),
             ("context.cuda.optix.enable", 0),     # LuxCore's OptiX accel fails to compile here; plain CUDA BVH
             ("opencl.devices.select", OPT.get("devices", "0011")),   # 0011: the two A100s through CUDA
             ("film.width", RES[0]), ("film.height", RES[1]), ("batch.halttime", HALT),
             ("film.imagepipelines.0.0.type", "NOP"),
             ("film.imagepipelines.0.1.type", "INTEL_OIDN" if OPT.get("denoise", "1") == "1" else "NOP"),
             ("film.imagepipelines.0.2.type", "TONEMAP_LINEAR"), ("film.imagepipelines.0.2.scale", float(OPT.get("exposure", 0.4 if OPT.get("shop", "0") == "1" else 0.3))),
             ("film.imagepipelines.0.3.type", "GAMMA_CORRECTION"), ("film.imagepipelines.0.3.value", 2.2),
             ("film.outputs.0.type", "ALPHA" if MODE == "mask" else "RGB_IMAGEPIPELINE"), ("film.outputs.0.filename", OUT),
             # albedo and normal passes: OIDN uses them as guides and keeps the emblem, paper grain and seams
             ("film.outputs.1.type", "ALBEDO"), ("film.outputs.1.filename", OUT.replace(".png", "_albedo.exr")),
             ("film.outputs.2.type", "AVG_SHADING_NORMAL"), ("film.outputs.2.filename", OUT.replace(".png", "_normal.exr"))):
    C.Set(pyluxcore.Property(k, v))
config = pyluxcore.RenderConfig(C, scene)
session = pyluxcore.RenderSession(config)
t0 = time.time()
session.Start()
while not session.HasDone():
    time.sleep(2)
    session.UpdateStats()
    if time.time() - t0 > HALT + 30:
        break
stats = session.GetStats()
print(f"{VIEW}: {stats.Get('stats.renderengine.pass').GetInt()} passes in {time.time() - t0:.0f} s, "
      f"{stats.Get('stats.renderengine.total.samplesec').GetFloat() / 1e6:.1f} Msamples/s", flush=True)
film = session.GetFilm()
film.Save()
for aux in ("_albedo.exr", "_normal.exr"):
    if os.path.exists(OUT.replace(".png", aux)):
        os.remove(OUT.replace(".png", aux))
if MODE != "mask":
    # the unclipped linear image (denoised, before gamma): the PNG is clipped at 1.0, which erased thin dark print on
    # over-lit paper before any highlight roll-off could act
    buf = np.zeros(RES[0] * RES[1] * 3, dtype=np.float32)
    film.GetOutputFloat(pyluxcore.FilmOutputType.RGB_IMAGEPIPELINE, buf)
    hdr = buf.reshape(RES[1], RES[0], 3)
    hdr = hdr[::-1]                                # LuxCore's float buffer runs bottom-up (checked against the PNG)
    hdr = np.maximum(hdr, 0) ** 2.2                # the pipeline ends in GAMMA_CORRECTION: back to linear, always
    #                                                (guessing per image made the plate and the render disagree)
    np.save(OUT.replace(".png", ".npy"), hdr.astype(np.float32))
session.Stop()
if MODE == "full" and OPT.get("flatbg", "1") == "1" and not SHOP:
    # clean plate: the empty studio (same lights) and a bottle alpha; the backdrop is divided by the plate and set on
    # the photos' 236 grey, so the floor/wall horizon cancels while the shadow and caustics survive as ratios; the
    # bottle takes the same exposure (plate's backdrop -> 236)
    import subprocess
    base = [sys.executable, os.path.abspath(__file__)] + [a for a in sys.argv[1:] if not a.startswith(("mode=", "out=", "time="))]
    plate_p, mask_p = OUT.replace(".png", "_plate.png"), OUT.replace(".png", "_mask.png")
    subprocess.run(base + ["mode=plate", f"out={os.path.relpath(plate_p, HERE)}", f"time={OPT.get('platetime', 20)}"], check=True)
    subprocess.run(base + ["mode=mask", f"out={os.path.relpath(mask_p, HERE)}", "time=8"], check=True)
    full, plate = np.load(OUT.replace(".png", ".npy")).astype(float), np.load(plate_p.replace(".png", ".npy")).astype(float)
    alpha = np.asarray(Image.open(mask_p).convert("L")).astype(float)[..., None] / 255
    bg = (236 / 255) ** 2.2
    border = np.concatenate([plate[: RES[1] // 12].reshape(-1, 3), plate[:, : RES[0] // 12].reshape(-1, 3)])
    k = bg / max(np.median(border.mean(axis=1)), 1e-6)
    bottle = full * k
    # highlight roll-off on luminance (keeps hue): above the knee, values compress smoothly toward white, so paper,
    # metal and glass several times over white keep their print, grain and edges
    knee = 0.75
    lum = (bottle @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
    over = np.maximum(lum - knee, 0)
    target = np.where(lum > knee, knee + (1 - knee) * over / (over + (1 - knee) * 2.5), lum)
    bottle = bottle * target / np.maximum(lum, 1e-6)
    out = alpha * bottle + (1 - alpha) * full / np.maximum(plate, 1e-6) * bg
    Image.fromarray((np.clip(out, 0, 1) ** (1 / 2.2) * 255).round().astype(np.uint8)).save(OUT)
    if OPT.get("keep", "0") != "1":                # keep=1: leave the plate and mask for inspection
        for f in (plate_p, mask_p, plate_p.replace(".png", ".npy")):
            os.remove(f)
    print(f"rendered {OUT} (clean plate, bottle gain {k:.2f})", flush=True)
else:
    print(f"rendered {OUT}", flush=True)
os._exit(0)                                       # skip pyluxcore's crash-prone interpreter teardown
