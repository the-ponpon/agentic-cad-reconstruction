"""Placeholder emblem for the cap engraving.

The original project traced the brand's emblem from the top photo into clean curves (see trace_emblem.py for the
method). That geometry is the brand's artwork, so it is not distributed here: this placeholder returns a simple
symmetric mark of the same size so parade.py still builds the engraved cap. Replace polygons() with your own trace.

    polygons() -> [(outer, holes)], coordinates in emblem units (the cap's across-flats width = 1), centred on 0
"""
import math


def polygons():
    """a ring and a bar: the placeholder mark"""
    ring_o = [(0.30 * math.cos(2 * math.pi * k / 64), 0.30 * math.sin(2 * math.pi * k / 64)) for k in range(64)]
    ring_i = [(0.24 * math.cos(2 * math.pi * k / 64), 0.24 * math.sin(2 * math.pi * k / 64)) for k in range(64)][::-1]
    bar = [(-0.16, -0.03), (0.16, -0.03), (0.16, 0.03), (-0.16, 0.03)]
    return [(ring_o, [ring_i]), (bar, [])]
