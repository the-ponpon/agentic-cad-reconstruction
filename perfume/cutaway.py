"""Vertical section of the bottle (plane y = 0, the front half removed), seen straight on from the front: the glass
solid shows red where it is cut (its back faces, seen through the cut, fill the wall section), its inner and outer
surfaces grey; the metal parts in a darker grey.      python cutaway.py -- out.png [res]"""
import math, os, sys
import bpy, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[sys.argv.index("--") + 1:]; OUT = args[0]; RES = int(args[1]) if len(args) > 1 else 2000
D = np.load(os.path.join(HERE, "blend/scene_export_meshes.npz"))
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene


def cutmat(name, front, back):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*front, 1); b.inputs["Roughness"].default_value = 0.55
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*back, 1); em.inputs["Strength"].default_value = 1.0
    geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "LESS_THAN"; gt.inputs[1].default_value = 0.0      # y < 0: removed
    mx = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx2 = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(geo.outputs["Backfacing"], mx.inputs["Fac"]); nt.links.new(b.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(geo.outputs["Position"], sep.inputs[0]); nt.links.new(sep.outputs["Y"], gt.inputs[0])
    nt.links.new(gt.outputs[0], mx2.inputs["Fac"]); nt.links.new(mx.outputs[0], mx2.inputs[1]); nt.links.new(tr.outputs[0], mx2.inputs[2])
    nt.links.new(mx2.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


GLASS = cutmat("glass_cut", (0.6, 0.62, 0.65), (0.85, 0.05, 0.04))
METAL = cutmat("metal_cut", (0.35, 0.35, 0.37), (0.12, 0.12, 0.13))
for part, m in (("glass", GLASS), ("collar", METAL), ("pump", METAL), ("cap", METAL), ("dip_tube", METAL), ("emblem_cap", METAL)):
    P, T = D[part + "_m__p"] * 0.001, D[part + "_m__t"]
    me = bpy.data.meshes.new(part); me.from_pydata(P.tolist(), [], T.tolist()); me.update()
    ob = bpy.data.objects.new(part, me); ob.data.materials.append(m); sc.collection.objects.link(ob)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = float(os.environ.get("WORLD", 0.8))
from mathutils import Vector
for loc, e in (((-0.15, -0.3, 0.25), float(os.environ.get("KEY", 25))), ((0.2, -0.25, 0.1), float(os.environ.get("KEY", 25)) * 0.4)):
    ld = bpy.data.lights.new("l", "AREA"); ld.size = 0.3; ld.energy = e
    o = bpy.data.objects.new("l", ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 0.06)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
cd = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
AZ, EL = float(os.environ.get("AZ", 0)), float(os.environ.get("EL", 0))
if AZ == 0 and EL == 0:                                     # the flat section, orthographic
    cd.type = "ORTHO"; cd.ortho_scale = 0.135
    cam.location = (0, -0.5, 0.058); cam.rotation_euler = (math.pi / 2, 0, 0)
else:                                                       # a 3D view into the cut: perspective, from front-left above
    tgt = Vector((0, 0.004, 0.056)); dist = 0.42; e, a_ = math.radians(EL), math.radians(-90 + AZ)
    cam.location = tgt + dist * Vector((math.cos(e) * math.cos(a_), math.cos(e) * math.sin(a_), math.sin(e)))
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    cd.sensor_fit = "VERTICAL"; cd.sensor_height = 24; cd.lens = float(os.environ.get("LENS", 55))
sc.render.engine = "CYCLES"; sc.cycles.samples = 64; sc.cycles.use_denoising = True
sc.cycles.transparent_max_bounces = 64
prefs = bpy.context.preferences.addons["cycles"].preferences; prefs.compute_device_type = "OPTIX"; prefs.get_devices()
for dv in prefs.devices: dv.use = True
sc.cycles.device = "GPU"; sc.view_settings.view_transform = "Standard"; sc.render.film_transparent = os.environ.get("TRANSP") == "1"
sc.render.resolution_x, sc.render.resolution_y = int(RES * 0.75), RES
sc.render.filepath = OUT; bpy.ops.render.render(write_still=True)
