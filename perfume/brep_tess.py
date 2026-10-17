"""The same B-rep glass, tessellated at three precisions (for the 'control over the simulation mesh' slide)."""
import numpy as np
src = open("parade.py").read()
exec(src[:src.index('os.makedirs("usd_parts"')])
import keel.io as kio
from keel._kernel import call
g = glass.scale(S)
for name, chord, ang in (("coarse", 0.5, 25.0), ("medium", 0.05, 8.0), ("fine", 0.005, 2.0)):
    poly = call("tessellate", kio.ub.tessellate, g.brep, chord_height_tolerance=chord,
                curve_angle_tolerance_deg=ang, surface_angle_tolerance_deg=ang)
    a = poly.to_mesh_arrays()
    flat, tris, i = a["faces"], [], 0
    while i < len(flat):
        k = flat[i]; idx = flat[i + 1:i + 1 + k]
        tris += [(idx[0], idx[j], idx[j + 1]) for j in range(1, k - 1)]; i += k + 1
    np.savez_compressed(f"story/tess_{name}.npz", points=np.asarray(a["points"]), normals=np.asarray(a["normals"]), tris=np.asarray(tris))
    print(name, chord, len(tris), "triangles")
