"""Render the three tessellations of the same B-rep (wireframe on white), same close-up camera on a top corner."""
import math, os, sys
import numpy as np
import bpy
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "SINGLE"
sc.display.shading.single_color = (0.93, 0.93, 0.92)
sc.display.shading.show_cavity = False
sc.render.resolution_x = sc.render.resolution_y = 900
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("w"); sc.world = w; w.color = (0.93, 0.925, 0.91)
sc.display.shading.background_type = "WORLD"
cd = bpy.data.cameras.new("c"); cd.lens = 85; cd.clip_start = 1
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
T = Vector((17.0, -17.0, 76.0))                    # top front-right corner and the shoulder dome (model mm)
cam.location = T + Vector((55, -85, 48))
cam.rotation_euler = (T - cam.location).to_track_quat("-Z", "Y").to_euler()
for name in ("coarse", "medium", "fine"):
    for o in list(sc.objects):
        if o.type == "MESH":
            bpy.data.objects.remove(o)
    d = np.load(os.path.join(HERE, "story", f"tess_{name}.npz"))
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in d["points"]], [], [tuple(t) for t in d["tris"]]); me.update()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    P_, T_ = d["points"], d["tris"]
    e = np.max(np.linalg.norm(P_[T_] - P_[np.roll(T_, 1, axis=1)], axis=2), axis=1)
    Tw = T_[e < 12.0]                                   # wireframe only: drop the long fan triangles of flat faces
    mw = bpy.data.meshes.new(name + "_w"); mw.from_pydata([tuple(v) for v in P_], [], [tuple(t) for t in Tw]); mw.update()
    wf = bpy.data.objects.new(name + "_w", mw); sc.collection.objects.link(wf)
    mod = wf.modifiers.new("w", "WIREFRAME"); mod.thickness = {"coarse": 0.12, "medium": 0.05, "fine": 0.02}[name]; mod.use_replace = True
    mat = bpy.data.materials.new("wire"); mat.diffuse_color = (0.18, 0.40, 0.80, 1); wf.data.materials.append(mat)
    sc.display.shading.color_type = "MATERIAL"
    base = bpy.data.materials.new("base"); base.diffuse_color = (1.0, 1.0, 1.0, 1); o.data.materials.append(base)
    sc.render.filepath = os.path.join(HERE, "story", f"tess_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, len(d["tris"]))
