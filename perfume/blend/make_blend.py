"""Build an editable Blender preview of the LuxCore shop scene (the layout handoff).

    Blender --background --python make_blend.py -- [scene_export.json] [out.blend]

Reads scene_export.json + scene_export_meshes.npz (written by parade_lux.py export=<file>) and the textures in tex/.
Every object is recreated in metres with a preview material, parented to one of four handles you can move, rotate or
scale: BOTTLE, COUNTER, WALL, BRANCH (or move the objects themselves). The camera "LuxCam" is the render camera (same
position, target, 100 mm lens on a 36 mm sensor across the long side, 1080x1350). Save the file and hand it back:
read_layout.py turns the object placements and the camera into layout.json for parade_lux.py layout=<file>.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SRC = args[0] if args else os.path.join(HERE, "scene_export.json")
OUT = args[1] if len(args) > 1 else os.path.join(HERE, "parade_shop_layout.blend")
d = json.load(open(SRC))
npz = np.load(os.path.splitext(SRC)[0] + "_meshes.npz")
TEX = os.path.join(HERE, "tex")
BOX = os.environ.get("REMOTE_DIR_ABS", "/path/on/render/host/parade/")   # where the exported texture paths pointed
SKIP = {"key", "fill", "fill_hi", "graze", "label_shop"}          # studio softboxes: light only, never seen

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def group_of(o):
    if o.startswith("cb_"):
        return "BRANCH"
    if o.startswith("counter_"):
        return "COUNTER"
    if o.startswith("w5_"):
        return "WALL"
    return "BOTTLE"


handles = {}
for g in ("BOTTLE", "COUNTER", "WALL", "BRANCH"):
    e = bpy.data.objects.new(g, None)
    e.empty_display_type = "PLAIN_AXES"; e.empty_display_size = 0.08
    sc.collection.objects.link(e)
    handles[g] = e


def image(tex):
    f = d["textures"].get(tex)
    if not f:
        return None
    p = os.path.join(TEX, f.replace(BOX, ""))
    return bpy.data.images.load(p, check_existing=True) if os.path.exists(p) else None


def fl(m, k, default):
    v = m.get(k)
    try:
        return [float(x) for x in v] if v else default
    except ValueError:
        return default


MATS = {}


def material(name):
    if name in MATS:
        return MATS[name]
    m = d["materials"].get(name, {})
    typ = (m.get("type") or ["matte"])[0]
    if typ == "glossycoating":                                     # preview the base
        return material(m["base"][0])
    mt = bpy.data.materials.new(name); mt.use_nodes = True
    nt = mt.node_tree; b = nt.nodes["Principled BSDF"]

    def col(field, default):
        v = m.get(field)
        if v and len(v) == 1 and image(v[0]) is not None:         # an image texture
            tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = image(v[0])
            return tx.outputs["Color"]
        c = fl(m, field, default)
        return (c + [1.0])[:4] if len(c) == 3 else default + [1.0]

    def set_in(inp, v):
        if hasattr(v, "is_output"):
            nt.links.new(v, b.inputs[inp])
        else:
            b.inputs[inp].default_value = v

    if typ == "glass":
        juice = name == "juice"
        b.inputs["Base Color"].default_value = (1.0, 0.80, 0.45, 1) if juice else (1, 1, 1, 1)
        b.inputs["Transmission Weight"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.0
        b.inputs["IOR"].default_value = 1.36 if juice else 1.5
        # the fast viewport can't refract: show the glass and liquid see-through so what is behind stays visible
        b.inputs["Alpha"].default_value = 0.35 if juice else 0.12
        try:
            mt.surface_render_method = "BLENDED"
        except AttributeError:
            mt.blend_method = "BLEND"
    elif typ == "metal2":
        b.inputs["Metallic"].default_value = 1.0
        b.inputs["Base Color"].default_value = (0.85, 0.86, 0.88, 1)
        b.inputs["Roughness"].default_value = fl(m, "uroughness", [0.1])[0]
    elif typ == "mattetranslucent":
        set_in("Base Color", col("kr", [0.8, 0.7, 0.75]))
        b.inputs["Subsurface Weight"].default_value = 0.3
        b.inputs["Roughness"].default_value = 0.7
    elif typ == "null":
        b.inputs["Alpha"].default_value = 0.0
    else:                                                          # matte / glossy2 / emissive panels
        kd = col("kd", [0.7, 0.7, 0.7])
        set_in("Base Color", kd)
        b.inputs["Roughness"].default_value = fl(m, "uroughness", [0.6])[0] if typ == "glossy2" else 0.8
        if "emission" in m:
            em = col("emission", [1, 1, 1])
            if hasattr(em, "is_output"):
                nt.links.new(em, b.inputs["Emission Color"])
            else:
                b.inputs["Emission Color"].default_value = em
            b.inputs["Emission Strength"].default_value = min(4.0, fl(m, "emission.gain", [1.0])[0] * 0.25)
    MATS[name] = mt
    return mt


for o, info in sorted(d["objects"].items()):
    if o in SKIP:
        continue
    sh = info["shape"]
    if sh + "__p" not in npz:
        continue
    p = npz[sh + "__p"].astype(float) * 0.001                       # mm -> m
    t = npz[sh + "__t"]
    me = bpy.data.meshes.new(sh)
    me.from_pydata(p.tolist(), [], t.tolist()); me.update()
    if sh + "__uv" in npz:
        uv = npz[sh + "__uv"]
        lay = me.uv_layers.new()
        for poly in me.polygons:
            for li in poly.loop_indices:
                u, v = uv[me.loops[li].vertex_index]
                lay.data[li].uv = (u, 1.0 - v)                    # LuxCore's v runs down
    ob = bpy.data.objects.new(o, me)
    sc.collection.objects.link(ob)
    ob.data.materials.append(material(info["material"]))
    ob.parent = handles[group_of(o)]

# the render camera
c = d["camera"]
cd = bpy.data.cameras.new("LuxCam"); cd.lens = c["lens"]; cd.sensor_width = 36.0; cd.sensor_fit = "AUTO"
cd.clip_start = 0.01; cd.clip_end = 50
cam = bpy.data.objects.new("LuxCam", cd); sc.collection.objects.link(cam); sc.camera = cam
eye = Vector(c["orig"]) * 0.001; tgt = Vector(c["target"]) * 0.001
cam.location = eye
cam.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
aim = bpy.data.objects.new("LuxCam_target", None); aim.empty_display_size = 0.02
aim.location = tgt; sc.collection.objects.link(aim)
tc = cam.constraints.new("TRACK_TO"); tc.target = aim; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
sc.render.resolution_x, sc.render.resolution_y = c["res"]

# preview lighting: a soft front light and a pale world (LuxCore uses the studio softboxes and the shop's own lights)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.82, 0.85, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
ld = bpy.data.lights.new("front", "AREA"); ld.size = 0.4; ld.energy = 60
lo = bpy.data.objects.new("front_light", ld); sc.collection.objects.link(lo)
lo.location = (0.3, -0.5, 0.35); lo.rotation_euler = (Vector((0, 0, 0.06)) - lo.location).to_track_quat("-Z", "Y").to_euler()
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        continue
sc["luxcore_opt"] = json.dumps(d["opt"])                            # what the export was rendered with
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
