"""Read an edited parade_shop_layout.blend back into a layout for the LuxCore render.

    Blender --background parade_shop_layout.blend --python read_layout.py -- layout.json

Writes, for every scene object, its world matrix (metres, column-major as LuxCore's .transformation wants it) and the
camera (eye, target, up in mm, lens in mm). parade_lux.py layout=layout.json applies both.
"""
import json
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "layout.json"
objs = {}
for ob in bpy.data.objects:
    if ob.type == "MESH":
        m = ob.matrix_world
        objs[ob.name] = [m[r][c] for c in range(4) for r in range(4)]          # column-major
cam = bpy.context.scene.camera
mw = cam.matrix_world
eye = mw.translation
fwd = -(mw.to_3x3().col[2]); up = mw.to_3x3().col[1]
tgt = bpy.data.objects.get("LuxCam_target")
dist = (tgt.matrix_world.translation - eye).length if tgt else 0.5
target = eye + fwd.normalized() * dist
json.dump({"objects": objs,
           "camera": {"orig": [v * 1000 for v in eye], "target": [v * 1000 for v in target], "up": list(up),
                      "lens": cam.data.lens, "focus_mm": dist * 1000}}, open(out, "w"), indent=1)
print("wrote", out, len(objs), "objects")
