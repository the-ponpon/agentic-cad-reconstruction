"""keel model of the Celine Parade 100 ml bottle (Haute Parfumerie), after the four product photos ref_<view>.png (front, three_quarter, neck, top).

Frame: X across the front, Y front -> back (the label face looks toward -Y), Z up, base at Z = 0. Scale from the
front photos. The 3/4 photo (ref_three_quarter) shows the gold reaching the outer edges of both faces and up to the shoulder,
so the walls are thin (~4 mm) except the 13 mm base; holding ~100 ml with such walls fixes the size. The model is
drawn at the front photo's proportions (body 66 wide) and scaled by S = 0.85 on export: body 56 x 44 x 83 mm,
about 120 mm tall with the cap.

    glass       thick square flacon, flanks slightly concave in plan, 15 mm clear base, a shallow round glass
                lens on the shoulder round the neck, liquid cavity fluted on the sides and back
    liquid      the cavity filled to 92 %, a hair smaller than the cavity so its faces don't touch the glass
    collar      polished metal: washer on the lens, stepped rings, sleeve
    pump        actuator with the Triomphe engraved on top and a spray hole; dip tube to the bottom
    cap         black, ten-sided, Triomphe engraved on top, hollow to clear the pump
    label       paper plate on the front face, with a raised border frame (print is a texture in Blender)

    keel parade.py  ->  parade_<part>.stl / .step, parade.usda (one prim per part), parade_parts.json
"""
import json
import math
import os
import subprocess

from keel import *

W, D, H = 66.0, 66.0, 106.0                     # glass body: SQUARE in plan (top photo); 1.61 x taller than wide (front photo)
SAG_LR, SAG_FB = 0.0, 0.0                       # straight sides: the base is a true rounded square (clay top view);
#                                                 the wavy outline in ref_top is refraction, not shape
FACE_Y = -D / 2 + SAG_FB                        # front face at its middle, where the label sits
CORNER = 3.0                                    # plan radius of the vertical corners (iteration 6: 6 read too round in ref_top)
BASE = 11.0                                      # clear glass under the liquid at the corners (ref_three_quarter: arches ~2x this)
S = float(os.environ.get("SCALE", 0.755))        # drawing -> real size, set so the flacon holds ~110 ml brim full
WALL = 4.0 / S                                  # 4 mm walls once scaled
# side walls follow a measured profile (side_profile): the cavity box is as wide as their thinnest, top part
SIDE_THICK, SIDE_THIN, FLARE_Z0, FLARE_Z1 = 7.4, 2.4, 76.0, 100.0   # ref_front left wall: 85 px (7.4) thick up to
#   z 76, the gold then flaring out to a 30 px (2.6) wall at z 100 (the inside curve visible near the shoulder)
CAV_W, CAV_D, CAV_Z0, CAV_Z1 = W - 2 * (SIDE_THIN - 0.6), D - 2 * WALL, BASE, H - 2.6   # box 0.6 proud of the profile
RIB_SWEEP = os.environ.get("RIB_SWEEP", "1") == "1"   # flutes swept along the flaring wall (else straight bars)
RIB_SCALE = float(os.environ.get("RIB_SCALE", 1.0))   # rib depth (0 = smooth cavity, for A/B tests); iteration 5: on
#   (ref_three_quarter shows strong vertical flutes through the side walls)
MESH_DIR = os.environ.get("MESH_DIR", "mesh")
FLUTE_PITCH, FLUTE_A = 6.0, 2.0                # inner ribs, near semicircular: each is a vertical lens that
#                                                 images the dome edge as one arch (the row of arches in ref_three_quarter)
NECK_R = 4.2                                    # bore through the neck
LENS_R, LENS_H = 26.5, 3.6                      # shoulder dome: footprint radius, and its rise under the cap (ref_front:
LENS_FLAT = 19.0                                # 3.5 units above the flat top); flat under the cap out to LENS_FLAT
COLLAR_Z = H + LENS_H
LW, LH, LZ0 = 39.2, 55.4, 39.2                  # paper edges in ref_front: x 676..1128, y 906..1546 (body 762 px = 66)
CAP_Z0, CAP_H, CAP_R = H + LENS_H + 0.2, 42.0, 20.0     # height 42: measured on the ref_front section overlay   # cap: 12 flats, circumradius CAP_R (39 across flats)


def merge(parts):
    out = parts[0]
    for p in parts[1:]:
        out = out + p
    return out


def cyl(r, z0, z1, x=0.0, y=0.0):
    return Cylinder(r, z1 - z0).move(x, y, (z0 + z1) / 2)


def prism(pts, z0, z1):
    return Polygon(*pts).on(Plane.at((0, 0, z0), (0, 0, 1), x_dir=(1, 0, 0))).extrude(z1 - z0)


def outline_arcs(w, d, sag_lr, sag_fb, r):
    """the flacon in plan from true arcs: a shallow concave arc per side, a round per corner (8 edges to fillet)"""
    corners = [(w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2), (-w / 2, -d / 2)]
    path, first = None, None
    for k in range(4):
        (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
        L = math.dist((x0, y0), (x1, y1))
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = -uy, ux
        sag = sag_lr if k % 2 == 0 else sag_fb
        a = (x0 + ux * r, y0 + uy * r)
        b = (x1 - ux * r, y1 - uy * r)
        m = ((a[0] + b[0]) / 2 + nx * sag, (a[1] + b[1]) / 2 + ny * sag)
        cx, cy = x1 - ux * r + nx * r, y1 - uy * r + ny * r
        e = (x1 + nx * r, y1 + ny * r)            # start of the next side
        q = (cx + r * (ux - nx) / math.sqrt(2), cy + r * (uy - ny) / math.sqrt(2))
        first = first or a
        if k == 3:
            e = first
        side = ThreePointArc(a, m, b) if sag > 1e-6 else Polyline(a, b)
        seg = side + ThreePointArc(b, q, e)
        path = seg if path is None else path + seg
    return path


def fluted_rect(w, d, r, pitch, amp, shrink=0.0, n=10):
    """the cavity in plan: rounded rectangle, glass ribs bulging in along the two sides and the back"""
    w, d, r, amp = w - 2 * shrink, d - 2 * shrink, max(r - shrink, 1.0), amp
    pts = []
    corners = [(w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2), (-w / 2, -d / 2)]
    for k in range(4):
        (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
        L = math.dist((x0, y0), (x1, y1))
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = -uy, ux
        fl = False                              # ribs are separate solids now (see ribs()); the outline stays plain
        flutes = max(1, round((L - 2 * r) / pitch))
        m = flutes * n if fl else n
        for i in range(m):
            t = r / L + (1 - 2 * r / L) * i / m
            u = (t - r / L) / (1 - 2 * r / L)                      # 0..1 along the straight part of the side
            s = amp * 0.5 * (1 - math.cos(2 * math.pi * flutes * u)) if fl else 0.0   # smooth rounded ribs
            pts.append((x0 + ux * L * t + nx * s, y0 + uy * L * t + ny * s))
        cx, cy = x1 - ux * r + nx * r, y1 - uy * r + ny * r
        a0 = math.atan2(-ny, -nx)
        for i in range(6):                       # the 7th point would be the next side's first
            a = a0 + math.pi / 2 * i / 6
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


WAIST_LR, WAIST_FB = 3.0, 2.0                  # inward bow of the cavity walls at mid-height (sides, front/back)
PLAN_BOW = float(os.environ.get("PLAN_BOW", 2.0))                                  # and in plan: each cavity side bows in 2 units at its middle (ref_top's clear
#                                                 rim is wider mid-side than at the corners); the outside stays square
DOME_H = 3.0    # floor: a shallow dome (ref_front: the gold's lower edge is 27 px = 2.3 units higher mid-width than at the sides)
FLOOR_R = 7.0   # its corners turn up into the walls with a large round (~5.5 units of rise at the walls)


RIB_VARY = [(1.00, 0.42), (0.55, 0.30), (0.80, 0.38), (0.45, 0.26), (0.95, 0.40), (0.60, 0.33), (0.75, 0.36)]
#           (relative depth, chord half-width as a fraction of the pitch): fixed, uneven, so no rib repeats its
#           neighbour's image (equal ribs printed a regular row of teeth in the top view and columns in the shoulder)


def ribs(shrink=0.0):
    """glass flutes on the two side walls (ref_three_quarter): vertical rounded bars standing proud of the wall, which
    is vertical up to FLARE_Z0 (side_profile); each runs from below the floor (buried in the base glass, so it bends
    into the curved floor) up to the flare, ending in a round cap. Uneven depth and width (RIB_VARY)."""
    d, r = CAV_D - 2 * shrink, 6.0
    n = max(1, round((d - 2 * r) / FLUTE_PITCH))
    seg = (d - 2 * r) / n
    xw = W / 2 - SIDE_THICK - shrink
    z_lo, z_hi = CAV_Z0 - FLOOR_DROP - 4.0, FLARE_Z0 + 2.0
    bars = []
    for sx in (-1, 1):
        for j in range(n):
            depth_f, half_f = RIB_VARY[(j + (3 if sx > 0 else 0)) % len(RIB_VARY)]
            amp = FLUTE_A * RIB_SCALE * depth_f
            half = half_f * seg
            rr = (half ** 2 + amp ** 2) / (2 * amp)
            cy = -d / 2 + r + (j + 0.5) * seg
            if RIB_SWEEP:
                # iteration 5b: the flute follows the wall up through the flare to the roof (ref_three_quarter: the
                # flutes run to the shoulder); a round tube swept along the wall's profile, its axis rr - amp out
                xp = W / 2 - SIDE_THIN + 0.5 - plan_offset(cy, 2 * (CAV_D / 2 + 0.5)) - shrink   # the plan bow caps the flare
                zs = [z_lo + (CAV_Z1 + 0.5 - z_lo) * i / 30 for i in range(31)]
                fade = lambda z: 1.0 - 0.85 * min(max((z - FLARE_Z0) / (CAV_Z1 - FLARE_Z0), 0.0), 1.0)   # noqa: E731
                # the flute's depth fades through the flare: full-depth tops under the roof read as a row of teeth in
                # the top view (preview review); ref_top shows a smooth wavy inner edge there
                pts = [(sx * (min(side_profile(z, shrink), xp) + rr - amp * fade(z)), cy, z) for z in zs]
                bars.append(Spline(*pts).pipe(rr))
            else:
                cx = sx * (xw + rr - amp)
                bars.append(cyl(rr, z_lo, z_hi, cx, cy) + Sphere(rr).move(cx, cy, z_hi))
    return merge(bars)


def ribs_iter3(shrink=0.0):
    """glass ribs on the two side walls, uneven in depth and width (the bands in ref_three_quarter vary). The side
    walls bow inward through the middle (waist_block); each rib is a torus section concentric with that bow, standing
    a constant depth proud of it, so it fades out by itself where the bow meets the straight wall above and below
    (straight ribs ran tangent to the bowed wall and broke the boolean)"""
    d, r = CAV_D - 2 * shrink, 6.0
    n = max(1, round((d - 2 * r) / FLUTE_PITCH))
    seg = (d - 2 * r) / n
    zm, wx, sag = (CAV_Z0 + CAV_Z1) / 2, waist_x(shrink), WAIST_LR + 0.5
    chord = CAV_Z1 - CAV_Z0 + 12.0
    R = (chord * chord / 4 + sag * sag) / (2 * sag)
    bars = []
    for sx in (-1, 1):
        for j in range(n):
            depth_f, half_f = RIB_VARY[(j + (3 if sx > 0 else 0)) % len(RIB_VARY)]
            amp = (FLUTE_A - shrink) * RIB_SCALE * depth_f      # rib depth alone scales; the walls stay put
            half = half_f * seg
            rr = (half ** 2 + amp ** 2) / (2 * amp)
            cy = -d / 2 + r + (j + 0.5) * seg
            tor = Torus(R + amp - rr, rr).rotate("X", 90)           # ring in the XZ plane, about an axis along Y
            dx = plan_offset(cy, 2 * (CAV_D / 2 - shrink + 0.5)) - 0.5   # the bowed wall has moved in here
            tor = tor.move(sx * (wx + R - sag - dx), cy, zm)
            near = Box(14, 2 * rr + 2, CAV_Z1 - CAV_Z0 + 10).move(sx * (wx - 4), cy, zm)   # only the arc at the wall:
            bars.append(tor.intersect(near))                                         # full rings would cross far away
    return merge(bars)


def waist_x(shrink=0.0):
    return (CAV_W + 2 * FLUTE_A) / 2 - shrink + 0.5


def side_profile(z, shrink=0.0):
    """half-width of the cavity at height z: constant (thick walls) up to FLARE_Z0, then flaring smoothly out to the
    thin top walls by FLARE_Z1"""
    t = min(max((z - FLARE_Z0) / (FLARE_Z1 - FLARE_Z0), 0.0), 1.0)
    return W / 2 - SIDE_THICK + (SIDE_THICK - SIDE_THIN) * (3 * t * t - 2 * t * t * t) - shrink


def waist_block(shrink=0.0):
    """side walls from the measured profile (a spline outline in XZ, extruded through the depth); the front and back
    walls bow inward by WAIST_FB at mid-height (an arc in YZ)"""
    z_lo, z_hi = CAV_Z0 - 12.0, CAV_Z1 + 12.0
    zs = [z_lo + (z_hi - z_lo) * i / 40 for i in range(41)]
    right = [(side_profile(z, shrink), z) for z in zs]
    left = [(-x, z) for x, z in reversed(right)]
    path = Spline(*right) + Polyline(right[-1], left[0]) + Spline(*left) + Polyline(left[-1], right[0])
    depth = 2 * (CAV_D / 2 - shrink) + 30.0
    return path.to_sketch().extrude(depth).rotate("X", 90).move(0, depth / 2, 0)


# floor (iteration 5, traced on ref_front): the gold's lower edge is HIGHEST mid-width (y 1836) and ~24 px (2.1 units)
# lower at +-19..22, then turns sharply up into the corners. So: a low dome in the middle (paraboloid, DOME_TOP at the
# axis, back to CAV_Z0 at DOME_R0) and a steep rise into each wall (floor blocks, from FLOOR_K of the half-width on)
DOME_TOP, DOME_R0 = 4.2, 27.0   # (7c: now a cylindrical arch across x, see dome_block)   # iteration 7b: one broad arch across the whole floor (ref_front: the gold's edge drops
#   2.1 between the middle and +-19 -> 4.2 at the axis with R0 27); the 18-radius dome read as a small ringed hump
FLOOR_RISE, FLOOR_DROP, FLOOR_K, FLOOR_P = 9.0, 4.0, 0.86, 2.0   # 7b: the corner lift only near the walls (pinched corners)


def floor_block(axis, shrink=0.0):
    """the curved floor seen in one direction: a block whose underside is z0 + rise * (|u| / half)^p, flat in the middle
    and sweeping up into the walls (the curved bottom of the gold in ref_front), extruded through the other direction"""
    half = (W / 2 - SIDE_THICK if axis == "x" else CAV_D / 2) - shrink
    z0 = CAV_Z0 + shrink - FLOOR_DROP
    us = [-(W / 2 + 2) + (W + 4) * i / 80 for i in range(81)]       # wider than the flared top walls
    bottom = [(u, z0 + FLOOR_RISE * (max(0.0, min(abs(u) / half, 1.15) - FLOOR_K) / (1 - FLOOR_K)) ** FLOOR_P) for u in us]
    top = CAV_Z1 + 20
    path = Spline(*bottom) + Polyline(bottom[-1], (bottom[-1][0], top), (bottom[0][0], top), bottom[0])
    depth = 2 * W + 40
    blk = path.to_sketch().extrude(depth).rotate("X", 90).move(0, depth / 2, 0)   # profile in XZ, through Y
    return blk if axis == "x" else blk.rotate("Z", 90)


def dome_block(shrink=0.0, axis="x"):
    """everything above the floor's arch (iteration 7c): z >= z0 + DOME_TOP * (1 - (x / DOME_R0)^2), a CYLINDRICAL arch
    across X, constant front to back. The revolved dome of 7/7b fell to ~0.6 at the front wall (r 25 of 27), and the
    gold's lower edge seen from the front is that front-wall line, so it read flat; the arch must run the full depth."""
    z0 = CAV_Z0 + shrink
    xs = [-(W / 2 + 2) + (W + 4) * i / 60 for i in range(61)]
    R0 = DOME_R0 if axis == "x" else DOME_R0 * (CAV_D / 2) / (W / 2 - SIDE_THICK)   # same arch on the deeper side faces
    prof = [(x, z0 + DOME_TOP * (1 - (x / R0) ** 2)) for x in xs]
    top = CAV_Z1 + 20
    path = Spline(*prof) + Polyline(prof[-1], (prof[-1][0], top), (prof[0][0], top), prof[0])
    depth = 2 * W + 40
    blk = path.to_sketch().extrude(depth).rotate("X", 90).move(0, depth / 2, 0)
    return blk if axis == "x" else blk.rotate("Z", 90)


FLOOR_SOFT = 0.6        # mm: blend width of the smooth floor (soft maximum of the arches and the wall lifts)


def floor_height(x, y, shrink=0.0):
    """the cavity floor as ONE smooth surface (iteration 7f): a soft maximum of the arch across x, the arch across y
    and the lift into each wall. Intersecting separate blocks (7-7e) left sharp creases where they met, refracted by
    the thick base into a V break at every vertical corner (reviewer, 45-degree renders)."""
    hx = DOME_TOP * (1 - (x / DOME_R0) ** 2)
    hy = DOME_TOP * (1 - (y / (DOME_R0 * (CAV_D / 2) / (W / 2 - SIDE_THICK))) ** 2)

    def lift(u, half):
        s_ = max(0.0, min(abs(u) / half, 1.15) - FLOOR_K) / (1 - FLOOR_K)
        return -FLOOR_DROP + FLOOR_RISE * s_ * s_

    k = FLOOR_SOFT
    if os.environ.get("FLOOR_MODE", "smooth") == "arch":   # the two arches only, no dip-and-rise at the walls
        vals = (hx, hy)
    else:
        vals = (hx, hy, lift(x, W / 2 - SIDE_THICK - shrink), lift(y, CAV_D / 2 - shrink))
    m = max(vals)
    return CAV_Z0 + shrink + m + k * math.log(sum(math.exp((v - m) / k) for v in vals))


def floor_loft(shrink=0.0, n_y=25, n_x=61):
    """everything above the smooth floor: a loft through XZ sections (placed along y), each closed by the roof line"""
    top = CAV_Z1 + 20
    half_y = CAV_D / 2 + 3.0
    secs = []
    for j in range(n_y):
        y = -half_y + 2 * half_y * j / (n_y - 1)
        xs = [-(W / 2 + 2) + (W + 4) * i / (n_x - 1) for i in range(n_x)]
        prof = [(x, floor_height(x, y, shrink)) for x in xs]
        path = Spline(*prof) + Polyline(prof[-1], (prof[-1][0], top), (prof[0][0], top), prof[0])
        secs.append(path.to_sketch().on(Plane.at((0, y, 0), (0, -1, 0), x_dir=(1, 0, 0))))
    return loft(*secs, smooth=True)


def fb_block(shrink=0.0):
    """front and back walls bowing inward by WAIST_FB at mid-height (kept separate from the side profile: subtracted
    from the same block the kernel fails the later intersect)"""
    h = CAV_Z1 - CAV_Z0
    zm = (CAV_Z0 + CAV_Z1) / 2
    chord = h + 12.0
    wy = CAV_D / 2 - shrink + 0.8   # 0.8 proud (was 0.5): with the cavity reaching lower (iteration 5) the kernel failed
    sag = WAIST_FB + 0.8            # the intersect at 0.5 for every chord tried; the bow itself is unchanged
    R = (chord * chord / 4 + sag * sag) / (2 * sag)
    blk = Box(W + 20, 2 * wy, chord + 20, align=("center", "center", "center")).move(0, 0, zm)
    for sgn in (-1, 1):
        blk = blk - Cylinder(R, 4 * W + 40).rotate("Y", 90).move(0, sgn * (wy + R - sag), zm)
    return blk


def smooth_outline(w, d, sag, r, n=240, sigma=1.6):
    """the bowed rounded rectangle as ONE tangent-continuous closed spline (iteration 7g). outline_arcs joins each
    bowed side to its corner round at ~14 deg (the side arc is not tangent to the corner arc): a vertical crease up
    every inner corner, seen magnified through the base as a vertical break (reviewer, 45-degree render). Sample the
    same outline, smooth it along its length (Gaussian, sigma in mm), resample, close with a spline."""
    hx, hy = w / 2, d / 2
    pts = []
    # corners (counter-clockwise), each side bowing inward by `sag` at its middle (parabolic), quarter-circle rounds
    corners = [(hx, -hy), (hx, hy), (-hx, hy), (-hx, -hy)]
    for k in range(4):
        (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
        L = math.dist((x0, y0), (x1, y1))
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = -uy, ux                                   # inward normal (counter-clockwise outline)
        for i in range(60):
            t = r / L + (1 - 2 * r / L) * i / 60
            u = (t - r / L) / (1 - 2 * r / L)
            bow = sag * 4 * u * (1 - u)
            pts.append((x0 + ux * L * t + nx * bow, y0 + uy * L * t + ny * bow))
        cx, cy = x1 - ux * r + nx * r, y1 - uy * r + ny * r
        a0 = math.atan2(-ny, -nx)
        for i in range(12):
            a_ = a0 + math.pi / 2 * i / 12
            pts.append((cx + r * math.cos(a_), cy + r * math.sin(a_)))
    P = __import__("numpy").array(pts)
    np_ = __import__("numpy")
    seg = np_.linalg.norm(np_.roll(P, -1, 0) - P, axis=1)
    s_ = np_.concatenate([[0], np_.cumsum(seg)[:-1]])
    total = seg.sum()
    su = np_.linspace(0, total, n, endpoint=False)
    out = []
    for sv in su:                                          # Gaussian smoothing along the closed arclength
        dd = (s_ - sv + total / 2) % total - total / 2
        wgt = np_.exp(-0.5 * (dd / sigma) ** 2)
        out.append(tuple((P * wgt[:, None]).sum(0) / wgt.sum()))
    return Spline(*(out + [out[0]]))


def plan_block(shrink=0.0):
    """the cavity's plan outline with each side bowed in by PLAN_BOW (true arcs, as the old exterior was), extruded
    tall: intersected with the cavity (cutting a box with vertical cylinders failed in the kernel)"""
    wx, wy = W / 2 - SIDE_THIN - shrink + 0.5, CAV_D / 2 - shrink + 0.5
    zm = (CAV_Z0 + CAV_Z1) / 2
    sk = smooth_outline(2 * wx, 2 * wy, PLAN_BOW + 0.5, 6.5).to_sketch()
    return sk.extrude(CAV_Z1 - CAV_Z0 + 60).move(0, 0, zm - (CAV_Z1 - CAV_Z0 + 60) / 2)


def plan_radius(span):
    chord = span + 8.0                                  # the arc meets the side's plane beyond the corners
    sag = PLAN_BOW + 0.5
    return (chord * chord / 4 + sag * sag) / (2 * sag)


def plan_offset(y, span):
    """how far the bowed side has moved in at position y along it"""
    Rp, sag = plan_radius(span), PLAN_BOW + 0.5
    return max(0.0, sag - (Rp - math.sqrt(max(Rp * Rp - y * y, 0.0))))


def cavity(shrink=0.0, z_top=CAV_Z1):
    """fluted prism; roof edges well rounded; floor domed up into the liquid (see below)"""
    z0, z1 = CAV_Z0 + shrink, CAV_Z1 - shrink
    zb = z0 - FLOOR_DROP - 2.0                   # the floor dips below CAV_Z0 next to the walls (floor blocks)
    body = RoundedRect(CAV_W - 2 * shrink, CAV_D - 2 * shrink, 6.0 - shrink).on(Plane.at((0, 0, zb), (0, 0, 1), x_dir=(1, 0, 0))).extrude(z1 + 2 - zb)   # true arcs; the box below sets the roof
    # roof rounding: a box 1 mm proud of the cavity on every side (coincident side faces break the intersect)
    rb = Box(CAV_W + 2 - 2 * shrink, CAV_D + 2 - 2 * shrink, z1 - zb + 1, align=("center", "center", "min")).move(0, 0, zb - 1)
    rb = rb.fillet(rb.faces(">Z")[0].edges(), 7.0 - shrink)   # 9 grazes the flutes and breaks the intersect
    c = body.intersect(rb)
    # walls first: the measured side profile (thick low, flaring at the top) and the front/back bow, then the plan bow;
    # the floor dome and its corner rounds come after, on the final walls
    c = c.intersect(fb_block(shrink))           # this order: two of the six orders fail in the kernel
    c = c.intersect(waist_block(shrink))
    c = c.intersect(plan_block(shrink))
    # floor: a low dome in the middle, sweeping steeply up into every wall (dome + two floor blocks)
    # cross vault (iteration 7e): the floor follows the HIGHER of two arches, one across x and one across y, so the
    # gold's lower edge arches on every face (front AND the side face seen in the three-quarter view). Intersecting
    # both = above the higher arch (a union kept the lower one and the front edge fell flat, measured in 7d).
    # Order ay, ax, fx, fy: the only one of 24 that passes the kernel.
    if os.environ.get("FLOOR_MODE", "smooth") == "flat":   # diagnostic: a plain flat floor (no break at the corners)
        pass
    else:
        c = c.intersect(floor_loft(shrink))         # 7f: one smooth floor surface (no creases)
    if RIB_SCALE > 0:                           # ribs after the waist: the other order fails to intersect
        c -= ribs(shrink)
    if z_top < z1:
        c = c.intersect(Box(200, 200, z_top - zb, align=("center", "center", "min")).move(0, 0, zb))
    return c


# --- glass -------------------------------------------------------------------------------------------------------
GLASS_EDGE = 3.0                                # soft round on the block's top and bottom edges (~2.5 mm real)
glass = outline_arcs(W, D, SAG_LR, SAG_FB, CORNER).to_sketch().extrude(H)
if SAG_LR > 1e-6 or SAG_FB > 1e-6:
    glass = glass.fillet(glass.edges("|Z"), 4.0)    # blend each concave flank into its corner round (tangent when straight)
for sel, r0 in ((">Z", GLASS_EDGE), ("<Z", 4.5)):  # one loop at a time (both at once fails); the base is rounder
    for r in (r0, GLASS_EDGE, 2.0, 1.2):
        try:
            glass = glass.fillet(glass.faces(sel)[0].edges(), r)
            print("glass", sel, "edge round", r)
            break
        except KeelError:
            continue
# the lens is a low raised disc with a crisp rounded rim (it catches a ring of light in ref_neck / ref_three_quarter)
# and a gently domed top; a bare spherical cap met the shoulder at a grazing angle and never showed an edge
def shoulder_dome():
    """the shoulder: a revolved profile, flat under the cap, falling as a cosine to the body top and tangent to it, so
    the rectangular body flows into the round surround with no step or rim (ref_front, ref_neck)"""
    pts = [(0.0, -0.6), (LENS_R + 0.6, -0.6)]
    for i in range(25):
        r = LENS_R - (LENS_R - LENS_FLAT) * i / 24
        pts.append((r, LENS_H * 0.5 * (1 - math.cos(math.pi * (LENS_R - r) / (LENS_R - LENS_FLAT)))))
    pts.append((0.0, LENS_H))
    path = Polyline(pts[0], pts[1]) + Spline(*pts[1:-1]) + Polyline(pts[-2], pts[-1], pts[0])
    return path.to_sketch().revolve(360, "Y").rotate("X", 90).move(0, 0, H)


glass += shoulder_dome()
# iteration 5b: a shallow hollow under the base (0.4 deep, 24 across radius): the flat underside parallel to the flat
# floor printed horizontal bands through the base in the front view, absent from ref_front
BASE_HOLLOW, BASE_HOLLOW_R = float(os.environ.get("BASE_HOLLOW", 0.4)), 24.0
_Rb = (BASE_HOLLOW_R ** 2 + BASE_HOLLOW ** 2) / (2 * BASE_HOLLOW) if BASE_HOLLOW > 0 else 0.0
if BASE_HOLLOW > 0:
    glass -= Sphere(_Rb).move(0, 0, BASE_HOLLOW - _Rb)
glass += cyl(8.0, H + LENS_H - 0.5, COLLAR_Z + 9.0)                      # threaded neck (under the collar)
if os.environ.get("SOLID", "0") != "1":           # SOLID=1 (diagnostic): the outer glass alone, no cavity
    glass -= cavity()
glass -= cyl(NECK_R, CAV_Z1 - 6, COLLAR_Z + 10)
# label recess: a rounded rectangle 1.2 units proud of the paper on every side, 0.5 deep (the thin golden rim and its
# rounded contour round the paper in ref_front)
# iteration 5: ref_front shows a framed panel: a bright line at the panel edge 2.9 units outside the paper, a ~2-unit
# strip, then a second line where the paper starts. So the recess has a sloped wall: floor 0.9 outside the paper,
# REC_D deep, its wall opening out to 2.9 at the face
REC_D, REC_FLOOR, REC_EDGE = 2.0, 0.9, 2.9
# iteration 7: the reviewer's "bevel around the label" is this recess wall: a bright sloped picture-frame rim round the
# paper (ref_front strip 642-666 px). 45 deg bevel from 2.9 outside the paper at the face to 0.9 outside at 2.0 deep,
# then the flat floor to the paper. (Iteration 5b's two vertical steps showed no rim.)
REC_TAPER = math.degrees(math.atan((REC_EDGE - REC_FLOOR) / REC_D))
_rk = RoundedRect(LW + 2 * REC_FLOOR, LH + 2 * REC_FLOOR, 1.2).on(Plane.at((0, FACE_Y + REC_D, LZ0 + LH / 2), (0, -1, 0), x_dir=(1, 0, 0)))
try:
    glass -= _rk.extrude(REC_D + 0.6, taper=-REC_TAPER)
    print("label recess: bevel", round(REC_TAPER, 1), "deg,", REC_D, "deep")
except KeelError as e:
    print("label recess: bevel failed, straight wall:", str(e)[:60])
    glass -= _rk.extrude(REC_D + 0.6)
print("glass", glass.is_valid, round(glass.volume * S ** 3 / 1000, 1), "cm3")

# filled to the brim like the photos (the air bubble sits up in the neck, under the collar): the roof is then a
# glass -> juice interface too, and there is no broad juice -> air surface for light to get trapped under
FILL_Z = CAV_Z1
liquid = cavity(0.0)
# the juice also fills the neck bore up to just under the collar's top: an air pocket in the bore showed through the
# shoulder dome as a bright oval (iteration-4 diagnostics: glass-only render)
liquid += cyl(NECK_R, CAV_Z1 - 1.0, COLLAR_Z + 6.0)
print("liquid", liquid.is_valid, round(liquid.volume * S ** 3 / 1000, 1), "ml")

# --- collar, pump, dip tube ----------------------------------------------------------------------------------
z = COLLAR_Z
# sprinkler, measured on ref_neck against the actuator (14.8 across): base disc 33, raised ring 30, neck ring 24,
# ferrule 21.6 x 14 tall with a rounded shoulder; the actuator drops into the ferrule's top
FERRULE_Z1 = z + 19.0                            # the middle sleeve is the tall part (ref_neck)


def rounded_cyl(r, z0, z1, top=0.0):
    c = cyl(r, z0, z1)
    return c.fillet(c.faces(">Z")[0].edges(), top) if top else c


# one revolved profile (r, height above the collar seat): flange, step ring, collar ring and the tall sleeve, with
# narrow grooves between them and small bevels on every edge (ref_neck); the actuator well leaves a thin dark gap
hs = FERRULE_Z1 - z
# iteration 6 (zoomed ref_neck + the reviewer's sketch): a short wide foot ring, then a TALL upper ring, then the
# sleeve; lower ring r 16.5, 2.0 tall; upper ring r 14.3, 3.35 tall; rounded top edges; a concave fillet from the upper
# ring's top face into the sleeve
COLLAR_PROFILE = [(0.0, -0.6), (16.2, -0.6), (16.45, -0.4), (16.5, -0.1),
                  (16.5, 0.9), (16.42, 1.15), (16.2, 1.35), (15.9, 1.42),                   # lower ring, rounded top
                  (14.75, 1.42), (14.75, 1.6),                                             # narrow groove
                  (14.3, 1.65), (14.3, 3.9), (14.22, 4.3), (14.0, 4.6), (13.65, 4.78), (13.2, 4.85),   # upper ring
                  (11.9, 4.85), (11.35, 4.95), (11.0, 5.2), (10.85, 5.6), (10.8, 6.1),     # concave fillet into the sleeve
                  (10.8, hs - 0.4), (10.4, hs), (0.0, hs)]                               # sleeve, bevelled top
collar = Polygon(*COLLAR_PROFILE).revolve(360, "Y").rotate("X", 90).move(0, 0, z)
collar -= cyl(8.1, z - 1, z + 9.5) + cyl(7.7, z + 9, FERRULE_Z1 + 1)      # neck finish below, actuator well on top
TRI = []                                         # Triomphe: two Cs back to back and an hourglass between them


def annular(cx, cy, r0, r1, a0, a1, n=28, sy=1.0):
    """an arc stroke between radii r0 and r1, from a0 to a1 deg; sy stretches it vertically (an elliptical C)"""
    pt = lambda r, a: (cx + r * math.cos(math.radians(a)), cy + sy * r * math.sin(math.radians(a)))  # noqa: E731
    return [pt(r1, a0 + (a1 - a0) * i / n) for i in range(n + 1)] + [pt(r0, a1 - (a1 - a0) * i / n) for i in range(n + 1)]


def offset_poly(pts, d):
    """closed polygon offset by d along the averaged vertex normals (outward for d > 0 on a CCW outline)"""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1 if area > 0 else -1
    out = []
    for i in range(n):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1, e2 = (x1 - x0, y1 - y0), (x2 - x1, y2 - y1)
        n1 = (e1[1], -e1[0])
        n2 = (e2[1], -e2[0])
        l1, l2 = math.hypot(*n1) or 1, math.hypot(*n2) or 1
        nx, ny = n1[0] / l1 + n2[0] / l2, n1[1] / l1 + n2[1] / l2
        ln = math.hypot(nx, ny) or 1
        out.append((x1 + sgn * d * nx / ln, y1 + sgn * d * ny / ln))
    return out


import emblem  # noqa: E402  (the Triomphe as clean curves, traced on ref_top)


def triomphe(size, z_top, depth, rot=0.0, flank=35.0):
    """engraving tool for the emblem: size = the emblem unit (the cap's across-flats width in the photo), turned rot
    degrees about Z; each stroke a shallow recess with walls flaring at `flank` deg, islands (the triangles) left
    standing with sloped walls"""
    c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def place(poly):
        pts = [(size * (x * c - y * s_), size * (x * s_ + y * c)) for x, y in poly]
        area = sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))
        return pts if area < 0 else pts[::-1]    # counter-clockwise: a clockwise loop extrudes downward, into the cap

    def pocket(poly, taper):
        sk = Polygon(*place(poly)).on(Plane.at((0, 0, z_top - depth), (0, 0, 1), x_dir=(1, 0, 0)))
        try:
            return sk.extrude(depth + 0.4, taper=taper)
        except KeelError:
            return sk.extrude(depth + 0.4)

    tools = []
    for outer, holes in emblem.polygons():
        t = pocket(outer, -flank)
        for h in holes:
            t -= Polygon(*place(h)).on(Plane.at((0, 0, z_top - depth - 0.1), (0, 0, 1), x_dir=(1, 0, 0))).extrude(depth + 0.6)
        tools.append(t)
    return tools                                 # cut one by one: unioned, the glyphs (their flared walls overlap the
                                                 # frame's) silently dropped out of the result


def emblem_beads(size, z_top, rot=0.0, r=0.12):
    """a thin round bead along every emblem outline, half sunk into the top: its rounded surface catches light from
    almost any direction, so the motif reads as fine bright contours (ref_top); a recessed groove's walls only see
    the inside of the groove"""
    c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    beads = []
    for outer, holes in emblem.polygons():
        for loop in [outer] + holes:
            pts = [(size * (x * c - y * s_), size * (x * s_ + y * c), z_top) for x, y in loop]
            pts = pts[:: max(1, len(pts) // 60)]
            try:
                beads.append(Spline(*(pts + [pts[0]])).pipe(r))
            except KeelError as e:
                print("   bead failed:", str(e)[:50])
    return beads


def engrave(part, tools, what):
    for k, t in enumerate(tools):
        try:
            cut_ = part - t
            if cut_.is_valid and cut_.volume < part.volume - 1e-6:
                part = cut_
            else:
                print(f"   {what}: emblem piece {k} left out (cut invalid or empty)")
        except KeelError as e:
            print(f"   {what}: emblem piece {k} failed: {str(e)[:60]}")
    return part


ACT_Z0, ACT_Z1, ACT_R = FERRULE_Z1 - 2.0, FERRULE_Z1 + 9.0, 7.4
pump = rounded_cyl(ACT_R, ACT_Z0, ACT_Z1, 0.7) + cyl(4.8, z + 9.5, ACT_Z0 + 0.5)
pump = engrave(pump, triomphe(15.0, ACT_Z1, 0.2, rot=44.3, flank=20.0), "actuator")   # 0.70 of the actuator across, axis to the neck camera (35 deg flanks: invalid at this scale)
NOZZLE_Z = ACT_Z1 - 3.6                          # round spray orifice: a shallow round recess, the hole at its centre
NOZZLE_AZ = -88.0                                 # ref_neck: 42 deg left of the face toward the camera (az -45.7)


def radial(rad, r0, r1):
    """a cylinder of radius rad along the outlet's radial axis, from r0 to r1 out from the actuator axis"""
    return Cylinder(rad, r1 - r0).rotate("Y", 90).move((r0 + r1) / 2, 0, NOZZLE_Z).rotate("Z", NOZZLE_AZ)


# the outlet (ref_neck: 0.19 of the actuator across): a round recess holding a separate pale insert, nearly flush,
# whose edge gap reads as a thin dark rim; the orifice at its centre
pump -= radial(1.45, ACT_R - 0.6, ACT_R + 0.5)
outlet = radial(1.2, ACT_R - 0.6, ACT_R - 0.08) - radial(0.22, ACT_R - 0.7, ACT_R)
print("pump", pump.is_valid)
dip = cyl(1.4, CAV_Z0 + DOME_TOP + 0.8, z + 10) - cyl(0.9, CAV_Z0 + DOME_TOP + 0.3, z + 11)   # clears the floor dome

# --- cap -------------------------------------------------------------------------------------------------------
CAP_SIDES = 12                                   # twelve facets (counted on ref_top), flats front/back/left/right
dodeca = [(CAP_R * math.cos(math.radians(15 + 30 * k)), CAP_R * math.sin(math.radians(15 + 30 * k))) for k in range(CAP_SIDES)]
cap = prism(dodeca, CAP_Z0, CAP_Z0 + CAP_H)
cap = cap.fillet(cap.edges("|Z"), 1.0)                                     # soft bevels between the facets
for sel, r in ((">Z", 0.9), ("<Z", 0.5)):                                   # rounded top and bottom rims
    try:
        cap = cap.fillet(cap.faces(sel)[0].edges(), r)
    except KeelError:
        cap = cap.chamfer(cap.faces(sel)[0].edges(), r * 0.6)
cap -= cyl(17.2, CAP_Z0 - 1, CAP_Z0 + CAP_H - 5)                          # clears collar and pump
cap = engrave(cap, triomphe(2 * CAP_R * math.cos(math.radians(15)), CAP_Z0 + CAP_H, 0.35, flank=45.0), "cap")
# 45 deg groove walls (iteration 5): looking straight down they mirror the horizon round the cap, where the top view's
# ring of strips sits, so each stroke is outlined by two bright lines (ref_top)
   # at the photo's own scale
print("cap", cap.is_valid)

# --- label ---------------------------------------------------------------------------------------------------
label = Box(LW, 0.35, LH, align=("center", "max", "min")).move(0, FACE_Y + REC_D - 0.01, LZ0)    # paper on the recess floor
# embossed border: a shallow raised frame on the paper (0.08 proud, soft-edged), 2.6 in from the edge, 0.7 wide;
# also in the bump map for its soft shoulders (iteration 3 kept it only in the bump and it vanished)
BORDER_IN, BORDER_W, BORDER_H = 2.6, 0.7, 0.08
pf = FACE_Y + REC_D - 0.36                            # the paper's front face
ring = (RoundedRect(LW - 2 * BORDER_IN, LH - 2 * BORDER_IN, 0.6) - RoundedRect(LW - 2 * BORDER_IN - 2 * BORDER_W,
        LH - 2 * BORDER_IN - 2 * BORDER_W, 0.3)).on(Plane.at((0, pf + 0.01, LZ0 + LH / 2), (0, -1, 0), x_dir=(1, 0, 0)))
frame = ring.extrude(BORDER_H + 0.01)
try:
    frame = frame.fillet(frame.faces("<Y")[0].edges(), 0.035)
except KeelError:
    pass
label += frame
print("label", label.is_valid)

PARTS = [("glass", glass, "glass"), ("liquid", liquid, "liquid"), ("collar", collar, "chrome"), ("pump", pump, "chrome"),
         ("dip_tube", dip, "clear_plastic"), ("outlet", outlet, "satin_insert"), ("cap", cap, "black_lacquer"), ("label", label, "paper")]
os.makedirs("usd_parts", exist_ok=True)
meta = []
for name, p, mat in PARTS:
    p = p.scale(S).named(name)
    print(f"{name:10s} valid {p.is_valid}  bbox {[round(v, 1) for v in p.bbox.min]} .. {[round(v, 1) for v in p.bbox.max]}")
    p.export(f"parade_{name}.stl", tolerance=0.02)
    try:
        p.export(f"parade_{name}.step")
    except KeelError as e:
        print("   no STEP:", e)
    p.export(f"usd_parts/{name}.usda")
    meta.append({"name": name, "material": mat})
# --- render meshes straight from the B-rep: fine tessellation and the surfaces' own normals ----------------------
import numpy as np  # noqa: E402
import keel.io as kio  # noqa: E402
from keel._kernel import call  # noqa: E402


def mesh_arrays(part, chord=0.005, angle=2.0):
    """points, exact surface normals and triangles of a part (fan-triangulating any polygon)"""
    poly = call("tessellate", kio.ub.tessellate, part.brep, chord_height_tolerance=chord,
                curve_angle_tolerance_deg=angle, surface_angle_tolerance_deg=angle)
    a = poly.to_mesh_arrays()
    flat, tris, i = a["faces"], [], 0
    while i < len(flat):
        n = flat[i]
        idx = flat[i + 1: i + 1 + n]
        tris += [(idx[0], idx[k], idx[k + 1]) for k in range(1, n - 1)]
        i += n + 1
    return np.asarray(a["points"], float), np.asarray(a["normals"], float), np.asarray(tris, np.int64)


def save_mesh(name, pts, nrm, tris):
    used = np.unique(tris)
    remap = -np.ones(len(pts), np.int64)
    remap[used] = np.arange(len(used))
    np.savez_compressed(f"{MESH_DIR}/{name}.npz", points=pts[used], normals=nrm[used], tris=remap[tris])
    return len(tris)


os.makedirs(MESH_DIR, exist_ok=True)
FZS = FILL_Z * S
for name, p, _ in PARTS:
    if name == "glass":
        continue
    print(f"mesh {name:10s}", save_mesh(name, *mesh_arrays(p.scale(S))), "triangles")
# the emblem's rounded lips, as render meshes: a thin tube along every engraved outline, centred on the top surface,
# in the part's own material. A recessed groove's walls only mirror the groove, and keel's fillets and pipe fuses on
# these tiny loops failed; the tubes give the fine bright contours of ref_top / ref_neck.
def lip_tubes(size, z_top, rot, r, n_ring=10):
    c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    P_, N_, T_ = [], [], []
    for outer, holes in emblem.polygons():
        for loop in [outer] + holes:
            q = np.array([(size * (x * c - y * s_), size * (x * s_ + y * c)) for x, y in loop])
            m = len(q)
            tan = np.roll(q, -1, axis=0) - np.roll(q, 1, axis=0)
            tan /= np.linalg.norm(tan, axis=1, keepdims=True)
            side = np.stack([-tan[:, 1], tan[:, 0]], axis=1)                  # in-plane normal
            base = len(P_)
            a = np.linspace(0, 2 * np.pi, n_ring, endpoint=False)
            for i in range(m):
                for t in a:
                    nrm = np.array([side[i, 0] * np.cos(t), side[i, 1] * np.cos(t), np.sin(t)])
                    P_.append([q[i, 0] + r * nrm[0], q[i, 1] + r * nrm[1], z_top + r * nrm[2]])
                    N_.append(nrm)
            for i in range(m):
                for j in range(n_ring):
                    a0, a1 = base + i * n_ring + j, base + i * n_ring + (j + 1) % n_ring
                    b0, b1 = base + ((i + 1) % m) * n_ring + j, base + ((i + 1) % m) * n_ring + (j + 1) % n_ring
                    T_ += [(a0, b1, b0), (a0, a1, b1)]   # outward winding (the reverse rendered the rims inside out)
    pts = np.array(P_, float) * S
    return pts, np.array(N_, float), np.array(T_, np.int64)


print("mesh emblem_cap", save_mesh("emblem_cap", *lip_tubes(2 * CAP_R * math.cos(math.radians(15)), CAP_Z0 + CAP_H, 0.0, 0.1)), "triangles")
print("mesh emblem_act", save_mesh("emblem_act", *lip_tubes(15.0, ACT_Z1, 44.3, 0.06)), "triangles")

# glass: drop the faces the liquid owns (the whole cavity: wet walls, plateau floor, roof); the neck bore above
# the roof stays glass -> air
pts, nrm, tris = mesh_arrays(glass.scale(S))
print("mesh glass_full", save_mesh("glass_full", pts, nrm, tris), "triangles (closed solid, for renderers with volume priorities)")
c = pts[tris].mean(axis=1)
cx, cy = (CAV_W / 2 + FLUTE_A) * S + 0.01, (CAV_D / 2 + FLUTE_A) * S + 0.01
wet = (np.abs(c[:, 0]) < cx) & (np.abs(c[:, 1]) < cy) & (c[:, 2] > (CAV_Z0 - FLOOR_DROP - 2) * S - 0.01) & (c[:, 2] < CAV_Z1 * S + 0.01)
print(f"glass: dropped {int(wet.sum())} wet triangles")
P_, N_, T_ = [pts], [nrm], [tris[~wet]]
print("mesh glass     ", save_mesh("glass", np.vstack(P_), np.vstack(N_), np.vstack(T_)), "triangles")

subprocess.run(["python", "usd_merge.py", "parade.usda"] + [f"usd_parts/{n}.usda" for n, *_ in PARTS], check=True)
json.dump({"parts": meta, "W": W * S, "D": D * S, "H": H * S, "fill_z": FILL_Z * S, "neck_r": NECK_R * S,
           "cavity": [(CAV_W / 2 + FLUTE_A) * S, (CAV_D / 2 + FLUTE_A) * S, CAV_Z0 * S, CAV_Z1 * S],
           "label": {"w": LW * S, "h": LH * S, "z0": LZ0 * S, "y": pf * S}},
          open("parade_parts.json", "w"), indent=1)
