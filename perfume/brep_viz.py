"""CAD-style picture of the B-rep for the post: white surfaces with a surface-following grid, and the exact B-rep
edges (face boundaries) as dark curves. python brep_viz.py [az=-52.8] [cut=1] [out=story/brep.png]
cut=1 shows the front half removed (meshes from cut_meshes.py) with the cut faces in red."""
import json, math, os, sys
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
A = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
S = 0.755
pose = json.load(open(os.path.join(HERE, "poses.json")))["three_quarter"]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def grid_material():
    m = bpy.data.materials.new("cad_grid"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.45
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], nsep.inputs[0])
    spacing, width = float(A.get("grid", 2.5)), float(A.get("lw", 0.10))
    acc = None
    for axis in ("X", "Y", "Z"):
        d = nt.nodes.new("ShaderNodeMath"); d.operation = "DIVIDE"; d.inputs[1].default_value = spacing
        nt.links.new(sep.outputs[axis], d.inputs[0])
        f = nt.nodes.new("ShaderNodeMath"); f.operation = "FRACT"; nt.links.new(d.outputs[0], f.inputs[0])
        s_ = nt.nodes.new("ShaderNodeMath"); s_.operation = "SUBTRACT"; s_.inputs[1].default_value = 0.5; nt.links.new(f.outputs[0], s_.inputs[0])
        a_ = nt.nodes.new("ShaderNodeMath"); a_.operation = "ABSOLUTE"; nt.links.new(s_.outputs[0], a_.inputs[0])
        g = nt.nodes.new("ShaderNodeMath"); g.operation = "GREATER_THAN"; g.inputs[1].default_value = 0.5 - width / spacing
        nt.links.new(a_.outputs[0], g.inputs[0])
        # a line family only on surfaces it crosses: skip it where the surface faces along that axis
        na = nt.nodes.new("ShaderNodeMath"); na.operation = "ABSOLUTE"; nt.links.new(nsep.outputs[axis], na.inputs[0])
        lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.75
        nt.links.new(na.outputs[0], lt.inputs[0])
        gm = nt.nodes.new("ShaderNodeMath"); gm.operation = "MULTIPLY"
        nt.links.new(g.outputs[0], gm.inputs[0]); nt.links.new(lt.outputs[0], gm.inputs[1]); g = gm
        if acc is None:
            acc = g
        else:
            mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
            nt.links.new(acc.outputs[0], mx.inputs[0]); nt.links.new(g.outputs[0], mx.inputs[1]); acc = mx
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs[6].default_value = (0.93, 0.93, 0.92, 1)      # surface
    mix.inputs[7].default_value = (0.25, 0.45, 0.80, 1)      # grid lines
    nt.links.new(acc.outputs[0], mix.inputs[0])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


def simple(name, rgb, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    return m


GRID = grid_material()
EDGE = simple("edge", (0.03, 0.05, 0.12), 0.6)
CUT = A.get("cut") == "1"            # cut=1: the front half removed (cut_meshes.py), the cut faces painted red
RED = simple("cutface", (0.80, 0.05, 0.04), 0.5)
for name in (("glass_full", "cap", "collar", "pump", "dip_tube") if CUT else ("glass_full", "cap", "collar", "pump", "label", "outlet")):
    p = os.path.join(HERE, "mesh_cut" if CUT else "mesh", f"{name}.npz")
    if not os.path.exists(p):
        continue
    d = np.load(p)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in d["points"]], [], [tuple(t) for t in d["tris"]])
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    o.data.materials.append(GRID)

if CUT:
    for name in ("glass_full", "cap", "collar", "pump", "dip_tube", "emblem_cap", "emblem_act"):
        p = os.path.join(HERE, "mesh_cut", f"{name}_capface.npz")
        if not os.path.exists(p):
            continue
        d = np.load(p); P_ = d["points"] + np.array([0, -0.03, 0])
        me = bpy.data.meshes.new(name + "_cap"); me.from_pydata([tuple(v) for v in P_], [], [tuple(t) for t in d["tris"]]); me.update()
        o = bpy.data.objects.new(name + "_cap", me); sc.collection.objects.link(o); o.data.materials.append(RED)
E = np.load(os.path.join(HERE, "brep_edges.npz"))
cu = bpy.data.curves.new("brep_edges", "CURVE"); cu.dimensions = "3D"
cu.bevel_depth = float(A.get("edge_r", 0.09)); cu.bevel_resolution = 2
n = 0
for k in E.files:
    if k == "kinds":
        continue
    P = E[k]
    runs = [P]
    if CUT:                                  # keep the parts of each edge behind the cut (y >= 0)
        keep = P[:, 1] >= 0; runs, cur = [], []
        for q, kp in zip(P, keep):
            if kp:
                cur.append(q)
            elif cur:
                runs.append(np.array(cur)); cur = []
        if cur:
            runs.append(np.array(cur))
    for R_ in runs:
        if len(R_) < 2:
            continue
        sp = cu.splines.new("POLY"); sp.points.add(len(R_) - 1)
        for i, q in enumerate(R_):
            sp.points[i].co = (q[0], q[1], q[2], 1)
        n += 1
eo = bpy.data.objects.new("brep_edges", cu); sc.collection.objects.link(eo); eo.data.materials.append(EDGE)
print("edges", n)

w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.84, 0.835, 0.82, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
for nm, loc, en in (("key", (300, -250, 350), 2.5e6), ("fill", (-300, -200, 150), 1.0e6)):
    ld = bpy.data.lights.new(nm, "AREA"); ld.size = 250; ld.energy = en
    lo = bpy.data.objects.new(nm, ld); sc.collection.objects.link(lo); lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 50)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

az, el = math.radians(float(A.get("az", pose["az"]))), math.radians(float(A.get("el", 25.0)))
t = Vector(pose["target"])           # poses are in the meshes' (scaled) millimetres
cd = bpy.data.cameras.new("cam"); cd.lens = 100; cd.sensor_width = 36; cd.sensor_height = 36; cd.sensor_fit = "VERTICAL"; cd.clip_start = 1   # LuxCore: 36 mm over the long side
co = bpy.data.objects.new("cam", cd); sc.collection.objects.link(co)
co.location = t + pose["dist"] * Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
co.rotation_euler = (t - co.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = co
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"; prefs.get_devices()
for dv in prefs.devices:
    dv.use = dv.type == "OPTIX"
sc.cycles.device = "GPU"; sc.cycles.samples = int(A.get("samples", 96)); sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
sc.render.filepath = os.path.join(HERE, A.get("out", "story/brep.png"))
os.makedirs(os.path.dirname(sc.render.filepath), exist_ok=True)
bpy.ops.render.render(write_still=True)
print("rendered", sc.render.filepath)
