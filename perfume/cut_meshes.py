"""Cut the bottle meshes with the plane y = 0 and keep the back half (y >= 0, the label side is -y), closing each
solid with a flat cap on the cut so the glass stays a closed dielectric. Writes mesh_cut/<name>.npz (points, normals,
tris; the cap included) and mesh_cut/<name>_capface.npz (the cap alone, for the red-painted section).
    python3 cut_meshes.py"""
import os
import numpy as np
from scipy.spatial import Delaunay
from matplotlib.path import Path

SRC, DST = "mesh", "mesh_cut"
os.makedirs(DST, exist_ok=True)
EPS = 1e-9


def clip(pts, nrm, tris):
    """keep y >= 0; split the triangles crossing y = 0 (positions and normals interpolated); return the kept mesh
    and the cut segments (pairs of points on y = 0)"""
    y = pts[:, 1]; s = y >= 0
    P, N = list(pts), list(nrm); T = []; segs = []
    cache = {}
    def cut(i, j):
        k = (min(i, j), max(i, j))
        if k not in cache:
            t = y[i] / (y[i] - y[j]); p = pts[i] + t * (pts[j] - pts[i]); p[1] = 0.0
            n = nrm[i] + t * (nrm[j] - nrm[i]); n /= np.linalg.norm(n) + EPS
            P.append(p); N.append(n); cache[k] = len(P) - 1
        return cache[k]
    for a, b, c in tris:
        ins = [s[a], s[b], s[c]]; n_in = sum(ins)
        if n_in == 3:
            T.append((a, b, c)); continue
        if n_in == 0:
            continue
        v = [a, b, c]
        k = ins.index(True) if n_in == 1 else ins.index(False)
        v0, v1, v2 = v[k], v[(k + 1) % 3], v[(k + 2) % 3]           # v0 is the odd one out, winding kept
        p01, p02 = cut(v0, v1), cut(v0, v2)
        if n_in == 1:
            T.append((v0, p01, p02)); segs.append((p01, p02))
        else:
            T += [(p01, v1, v2), (p01, v2, p02)]; segs.append((p02, p01))
    return np.array(P), np.array(N), np.array(T, np.int64), segs


def loops(segs):
    nxt = {}
    for a, b in segs:
        nxt.setdefault(a, b)
    out, seen = [], set()
    for start in list(nxt):
        if start in seen:
            continue
        lp, cur = [], start
        while cur in nxt and cur not in seen:
            seen.add(cur); lp.append(cur); cur = nxt[cur]
        if len(lp) > 2:
            out.append(lp)
    return out


def cap(P, segs):
    """triangulate the cut region on y = 0 (x, z): Delaunay of the loop points, keep triangles inside (even-odd)"""
    lps = loops(segs)
    if not lps:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    idx = np.concatenate(lps); xz = P[idx][:, [0, 2]]
    paths = [Path(P[l][:, [0, 2]]) for l in lps]
    tri = Delaunay(xz).simplices
    cen = xz[tri].mean(1)
    inside = np.zeros(len(tri), bool)
    for pa in paths:
        inside ^= pa.contains_points(cen)
    tri = tri[inside]
    V = P[idx].copy()
    # orient towards -y (the cap faces the viewer side)
    a, b, c = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]
    flip = np.cross(b - a, c - a)[:, 1] > 0
    tri[flip] = tri[flip][:, ::-1]
    return V, tri


for name in ("glass_full", "collar", "pump", "cap", "dip_tube", "outlet", "emblem_cap", "emblem_act"):
    m = np.load(os.path.join(SRC, name + ".npz"))
    pts, nrm, tris = m["points"].astype(float), m["normals"].astype(float), m["tris"].astype(np.int64)
    P, N, T, segs = clip(pts, nrm, tris)
    V, CT = cap(P, segs)
    CN = np.tile([0.0, -1.0, 0.0], (len(V), 1))
    allP = np.vstack([P, V]); allN = np.vstack([N, CN]); allT = np.vstack([T, CT + len(P)]) if len(CT) else T
    used = np.unique(allT); remap = -np.ones(len(allP), np.int64); remap[used] = np.arange(len(used))
    np.savez(os.path.join(DST, name + ".npz"), points=allP[used], normals=allN[used], tris=remap[allT])
    if len(CT):
        np.savez(os.path.join(DST, name + "_capface.npz"), points=V, normals=CN, tris=CT)
    print(f"{name:11s} kept {len(T)} tris, cut loops {len(loops(segs))}, cap {len(CT)} tris")
