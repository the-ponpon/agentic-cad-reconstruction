"""Merge single-part .usda files (keel export of one Part each) into one file, one named BrepArray prim per part.

keel.export(parts, x.usda) appends every part after the first into a single prim, so names are lost; this
writes each part on its own and splices the prims under /World.  usage: usd_merge.py out.usda in1.usda ...
"""
import sys

out, ins = sys.argv[1], sys.argv[2:]
head, prims = None, []
for path in ins:
    lines = open(path).read().split("\n")
    w = next(i for i, l in enumerate(lines) if l.startswith("def Xform \"World\""))
    if head is None:
        head = lines[: w + 2]  # header, def Xform "World", "{"
    end = max(i for i, l in enumerate(lines) if l == "}")
    prims.append("\n".join(lines[w + 2: end]))
open(out, "w").write("\n".join(head) + "\n" + "\n\n".join(prims) + "\n}\n")
print("merged", len(prims), "prims into", out)
