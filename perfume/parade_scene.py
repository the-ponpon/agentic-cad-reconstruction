"""Blender scene for the keel Parade bottle (parade.py), lit and framed like the product photos.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P parade_scene.py -- [view=front|three_quarter|top|neck]
        [res=WxH] [samples=N] [out=name.png] [blend]

Thick glass done properly: the glass mesh loses its wet cavity faces, so the liquid's surface there is the single
glass -> juice interface (relative IOR 1.36/1.52); the meniscus is air -> juice; the gold is volume absorption.
Materials: clear flint glass, amber juice, polished chrome collar and pump, black lacquer
cap, linen-grain paper label printed from label_print.png (make_label.py), clear dip tube. A warm light-grey sweep
with a soft floor shadow and two tall strip softboxes that draw the white bands on the cap and the glass edges.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OPT = dict(a.split("=", 1) for a in ARGS if "=" in a)
VIEW = OPT.get("view", "front")
RES = [int(v) for v in OPT.get("res", "900x1125").split("x")]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
info = json.load(open(os.path.join(HERE, "parade_parts.json")))


def principled(name, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        b.inputs[k.replace("_", " ")].default_value = (*v, 1) if k == "Base_Color" else v
    return m, m.node_tree, b


def obj_coords(nt):
    return nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]


MATS = {}
MATS["glass"] = principled("flint_glass", Base_Color=(0.97, 0.99, 0.98), Roughness=0.0, IOR=1.52, Transmission_Weight=1.0)[0]

N_GLASS, N_JUICE = 1.52, 1.36


def juice(name, ior):
    m, nt, b = principled(name, Base_Color=(1.0, 0.97, 0.9), Roughness=0.0, IOR=ior, Transmission_Weight=1.0)
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")  # the gold deepens with thickness (mm units)
    # green absorbed at ~0.15 x the blue rate: gold through the body; the very long paths under the meniscus
    # (total internal reflection) go amber, not red (~0.25 reddens them, ~0.06 turns short paths lemon-green)
    # from the photos: ~0.45 blue / 0.8 green through the 40 mm front path, still a light gold through the 64 mm
    # top-down path -> blue 0.020/mm, green 0.0056/mm (absorption = density x (1 - colour))
    vol.inputs["Color"].default_value = (1.0, 0.813, 0.333, 1)
    vol.inputs["Density"].default_value = float(OPT.get("density", 0.035))
    nt.links.new(vol.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    return m


MATS["liquid"] = juice("juice_glass_interface", N_JUICE / N_GLASS)   # wet walls: glass -> juice, relative IOR 0.895
MATS["juice_air"] = juice("juice_air_meniscus", N_JUICE)              # free surface under the shoulder: air -> juice
MATS["chrome"] = principled("polished_chrome", Base_Color=(0.93, 0.93, 0.95), Metallic=1.0, Roughness=0.04)[0]
MATS["black_lacquer"] = principled("black_lacquer", Base_Color=(0.004, 0.004, 0.005), Roughness=0.05, Coat_Weight=1.0,
                                   Coat_Roughness=0.02)[0]
MATS["clear_plastic"] = principled("clear_dip_tube", Base_Color=(0.95, 0.95, 0.95), Roughness=0.15, IOR=1.49,
                                   Transmission_Weight=1.0)[0]

# paper: linen grain bump, print over it from the label image, mapped by object coordinates (x across, z up)
m, nt, b = principled("label_paper", Base_Color=(0.93, 0.93, 0.91), Roughness=0.85, Sheen_Weight=0.3)
L = info["label"]
co = obj_coords(nt)
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(co, sep.inputs[0])
u = nt.nodes.new("ShaderNodeMath")
u.operation, u.inputs[1].default_value = "MULTIPLY_ADD", 1 / L["w"]
u.inputs[2].default_value = 0.5
nt.links.new(sep.outputs["X"], u.inputs[0])
v = nt.nodes.new("ShaderNodeMath")
v.operation, v.inputs[1].default_value = "MULTIPLY_ADD", 1 / L["h"]
v.inputs[2].default_value = -L["z0"] / L["h"]
nt.links.new(sep.outputs["Z"], v.inputs[0])
uv = nt.nodes.new("ShaderNodeCombineXYZ")
nt.links.new(u.outputs[0], uv.inputs["X"])
nt.links.new(v.outputs[0], uv.inputs["Y"])
img = nt.nodes.new("ShaderNodeTexImage")
img.image = bpy.data.images.load(os.path.join(HERE, "label_print.png"))
img.extension = "CLIP"
nt.links.new(uv.outputs[0], img.inputs["Vector"])
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = "RGBA"
mix.inputs["A"].default_value = (0.93, 0.93, 0.91, 1)
mix.inputs["B"].default_value = (0.02, 0.02, 0.02, 1)
nt.links.new(img.outputs["Alpha"], mix.inputs["Factor"])
nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
for scale, strength in ((3.2, 0.12), (0.9, 0.06)):     # woven linen: fine warp/weft ripples + a softer mottle
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type = "BANDS"
    w.inputs["Scale"].default_value, w.inputs["Distortion"].default_value = scale, 1.5
    nt.links.new(co, w.inputs["Vector"])
    bm = nt.nodes.new("ShaderNodeBump")
    bm.inputs["Strength"].default_value, bm.inputs["Distance"].default_value = strength, 0.05
    nt.links.new(w.outputs["Fac"], bm.inputs["Height"])
    if b.inputs["Normal"].is_linked:
        nt.links.new(b.inputs["Normal"].links[0].from_socket, bm.inputs["Normal"])
    nt.links.new(bm.outputs["Normal"], b.inputs["Normal"])
MATS["paper"] = m

import numpy as np  # noqa: E402

objs = {}
for p in info["parts"]:  # meshes tessellated from the B-rep at 2 deg / 5 um, with the surfaces' exact normals
    m = np.load(os.path.join(HERE, "mesh", f"{p['name']}.npz"))
    me = bpy.data.meshes.new(p["name"])
    me.from_pydata(m["points"].tolist(), [], m["tris"].tolist())
    me.shade_smooth()
    # per-corner normals: the B-rep's own normal where the surface is smooth; across a sharp edge (the cap's flats,
    # where the tessellator shares one vertex between faces) the triangle's own normal, so facets stay crisp
    pts, vn, tris = m["points"], m["normals"], m["tris"]
    fn = np.cross(pts[tris[:, 1]] - pts[tris[:, 0]], pts[tris[:, 2]] - pts[tris[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    corner = vn[tris]                                            # (n, 3 corners, 3)
    sharp = np.einsum("ncj,nj->nc", corner, fn) < math.cos(math.radians(8))   # 2 deg tessellation: smooth stays within ~3
    corner[sharp] = np.repeat(fn[:, None, :], 3, axis=1)[sharp]
    me.normals_split_custom_set(corner.reshape(-1, 3).tolist())  # loops follow the triangles' corner order
    o = bpy.data.objects.new(p["name"], me)
    scene.collection.objects.link(o)
    o.data.materials.append(MATS[p["material"]])
    objs[p["name"]] = o

for n in OPT.get("hide", "").split(","):            # diagnostics: hide=glass,label ...
    if n in objs:
        objs[n].hide_render = True

# --- nested dielectrics: parade.py already removed the glass faces the liquid owns (wet wall, dome floor), so the
# liquid's surface there is the single glass -> juice interface; its only free surface is the disc in the neck bore
import bmesh  # noqa: E402

FZ = info["fill_z"]
lq = objs["liquid"]
lq.data.materials.append(MATS["juice_air"])
top = 0
for poly in lq.data.polygons:
    if poly.normal.z > 0.99 and poly.center.z > FZ - 0.01 and math.hypot(poly.center.x, poly.center.y) < info["neck_r"] + 0.05:
        poly.material_index = 1
        top += 1
print("liquid: meniscus faces", top)

# --- studio: warm light-grey sweep, soft floor shadow, strip boxes -------------------------------------------
# cyclorama: floor curving up into the back wall, so the light-grey runs seamlessly behind the bottle
prof = [(y, 0.0) for y in (-3000, 150)] + [(150 + 300 * math.sin(t * math.pi / 2 / 12), 300 - 300 * math.cos(t * math.pi / 2 / 12))
                                             for t in range(1, 13)] + [(450, 3000)]
bm = bmesh.new()
rows = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in (-3000, 3000)]
for i in range(len(prof) - 1):
    bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
me = bpy.data.meshes.new("sweep")
bm.to_mesh(me)
bm.free()
sweep = bpy.data.objects.new("sweep", me)
scene.collection.objects.link(sweep)
sweep.location.z = -0.2   # an air gap under the base: with the floor on the glass, the base can't reflect internally
for poly in me.polygons:
    poly.use_smooth = True
# mostly self-lit, so floor and wall read as one even light grey like the photos; the diffuse part keeps the shadow
sw, swt, swb = principled("sweep", Base_Color=(0.12, 0.12, 0.118), Roughness=0.95, Emission_Strength=float(OPT.get("glow", 0.6)))
swb.inputs["Emission Color"].default_value = (1.0, 0.99, 0.97, 1)   # a faint glow evens the sweep out to the horizon
sweep.data.materials.append(sw)
for sx in (-1, 1):  # black flags just out of frame: the glass edges reflect them as dark lines
    bpy.ops.mesh.primitive_plane_add(size=1)
    fl = bpy.context.object
    fl.name = f"flag_{'L' if sx < 0 else 'R'}"
    fl.scale = (1, 160, 420)
    fl.location = (sx * 120, 60, 150)
    fl.rotation_euler = (0, math.radians(90), math.radians(-sx * 20))
    fl.data.materials.append(principled("flag_black", Base_Color=(0.0, 0.0, 0.0), Roughness=1.0)[0])
world = bpy.data.worlds.new("studio")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.9, 0.9, 0.89, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35


def area(name, loc, size, energy, aim=(0, 0, 70)):
    lt = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
    lt.data.shape, lt.data.size, lt.data.size_y = "RECTANGLE", size[0], size[1]
    lt.data.energy = energy
    lt.location = Vector(loc)
    lt.rotation_euler = (Vector(aim) - lt.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(lt)
    return lt


# a facet edge faces the camera: the two front facets at +-18 deg mirror strips at ~36 deg off the camera axis
area("strip_left", (-176, -243, 140), (40, 420), 1.5e5)   # the photo shows one bright band, right of centre
area("strip_right", (176, -243, 140), (40, 420), 4.0e5)
top_light = area("top", (0, 40, 520), (380, 380), float(OPT.get("top", 2.0e5)))
# light linking: the strips, top and back lights shape the bottle only, so the sweep stays one even grey (no bright
# floor band under a darker wall); a big soft key from the right lights everything and gives the photos' soft shadow
bottle = bpy.data.collections.new("bottle")
for o in objs.values():
    bottle.objects.link(o)
for lt in [o for o in scene.objects if o.type == "LIGHT"]:
    lt.light_linking.receiver_collection = bottle
area("key", (260, -120, 380), (320, 320), float(OPT.get("key", 2.5e5)))
area("back", (0, 260, 120), (260, 300), 9.0e5)          # glows through the glass and the juice, as in the photos

# --- camera ------------------------------------------------------------------------------------------------------
VIEWS = {  # (direction from the target to the camera, target, lens mm, distance), framed like the photos
    "front": ((0, -1, 0.06), (0, 0, 56), 100, 395),         # bottle ~79 % of the frame height
    "three_quarter": ((0.45, -0.78, 0.36), (0, 0, 50), 100, 400),
    "top": ((0.0, -0.001, 1), (0, 0, 60), 100, 290),
    "neck": ((0.55, -0.62, 0.62), (2, 0, 92), 100, 150),
}
d, tgt, lens, dist = VIEWS[VIEW]
cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens, cam.data.clip_start, cam.data.clip_end = lens, 5, 20000
cam.location = Vector(tgt) + Vector(d).normalized() * dist
cam.rotation_euler = (Vector(tgt) - cam.location).to_track_quat("-Z", "Y").to_euler()
if VIEW == "neck":
    objs["cap"].hide_render = True                      # the close-up photo shows the pump with the cap off
if VIEW == "top":
    top_light.data.energy = 0.0   # overhead it would sit right behind the camera and grey out the black lacquer
if VIEW == "neck":
    objs["cap"].hide_render = True                      # the close-up photo shows the pump with the cap off
if VIEW == "three_quarter":
    objs["cap"].rotation_euler.z = math.radians(9)      # a facet toward the camera, as in the photo

scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev in ("OPTIX", "METAL", "CUDA"):
    try:
        prefs.compute_device_type = dev
        break
    except TypeError:
        continue
prefs.get_devices()
for dv in prefs.devices:
    dv.use = True
scene.cycles.device = "GPU"
scene.cycles.samples = int(OPT.get("samples", 256))
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 32
scene.cycles.transmission_bounces = 32
scene.cycles.transparent_max_bounces = 32
scene.cycles.volume_bounces = 4
scene.cycles.caustics_refractive = True
scene.cycles.caustics_reflective = True
scene.cycles.blur_glossy = 0.0
scene.cycles.sample_clamp_indirect = 0.0                # unclamped, so the refracted gold light keeps its strength
scene.render.resolution_x, scene.render.resolution_y = RES
scene.view_settings.view_transform = "Standard"         # AgX greys out the gold
scene.view_settings.look = "None"
scene.view_settings.exposure = float(OPT.get("exposure", 0.0))
if "blend" in ARGS:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "parade.blend"))
out_path = os.path.join(HERE, OPT.get("out", f"parade_{VIEW}.png"))
scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)
print("rendered", out_path)
if OPT.get("flatbg", "1") == "1":
    # clean plate: the empty sweep (same light) and a holdout mask of the bottle; outside the bottle the render is
    # divided by the plate and set on the photos' even grey, so the floor/wall horizon cancels while the bottle's
    # shadow and the caustics on the floor survive as ratios to the plate
    import numpy as np
    full = np.array(bpy.data.images.load(out_path).pixels[:]).reshape(RES[1], RES[0], 4)[..., :3]
    keep = scene.cycles.samples
    scene.cycles.samples = 64
    for o in objs.values():
        o.hide_render = True
    scene.render.filepath = out_path.replace(".png", "_plate.png")
    bpy.ops.render.render(write_still=True)
    plate = np.array(bpy.data.images.load(scene.render.filepath).pixels[:]).reshape(RES[1], RES[0], 4)[..., :3]
    for n, o in objs.items():
        o.hide_render = n in OPT.get("hide", "").split(",")
        o.is_holdout = True
    scene.render.film_transparent = True
    scene.cycles.samples = 16
    scene.render.filepath = out_path.replace(".png", "_mask.png")
    bpy.ops.render.render(write_still=True)
    alpha = np.array(bpy.data.images.load(scene.render.filepath).pixels[:]).reshape(RES[1], RES[0], 4)[..., 3:4]
    scene.cycles.samples = keep
    bg = np.array([236, 236, 235]) / 255.0
    flat = np.clip(full / np.maximum(plate, 1e-3) * bg, 0, 1)
    out = alpha * flat + (1 - alpha) * full      # alpha = 1 on the backdrop, 0 over the bottle (holdout)
    img = bpy.data.images.load(out_path)
    px = np.concatenate([out, np.ones((RES[1], RES[0], 1))], axis=2)
    img.pixels[:] = px.ravel()
    img.save()
    for f in ("_plate.png", "_mask.png"):
        os.remove(out_path.replace(".png", f))
    print("flattened background", out_path)
