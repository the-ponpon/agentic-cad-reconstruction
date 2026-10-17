"""Sample every B-rep edge of the main parts into polylines (for the CAD-style picture in the post video).

    keel brep_edges.py  ->  brep_edges.npz (one polyline per edge, scaled like the meshes)
"""
import numpy as np
src = open("parade.py").read()
exec(src[:src.index('os.makedirs("usd_parts"')])
lines, kinds = [], []
for name, part in (("glass", glass), ("cap", cap), ("collar", collar), ("pump", pump), ("label", label)):
    p = part.scale(S)
    n_e = 0
    for e in p.edges():
        a, b = e._h.parameter_range()
        k = max(4, min(120, int(e.length / 0.4)))
        pts = []
        for i in range(k + 1):
            try:
                pts.append(tuple(e._h.point_at(a + (b - a) * (0.001 + 0.998 * i / k))))
            except RuntimeError:
                pass
        if len(pts) < 2:
            pts = [e.start, e.mid, e.end]
        lines.append(np.array(pts, float))
        kinds.append(name)
        n_e += 1
    print(name, n_e, "edges,", len(p.faces()), "faces")
np.savez_compressed("brep_edges.npz", *lines, kinds=np.array(kinds))
print("total", len(lines), "edges")
