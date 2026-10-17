# Photo → CAD → photoreal render: reconstruction playbook

Distilled from a thick-glass perfume bottle reconstruction, which went through several review iterations against
four product photos, and extended with a diamond pavé ring (three photos). Use this for any object that must be
modelled from reference photos and rendered to match them.

**Known limit.** The geometry is still built from simple primitives (extrusions, revolutions, lofts, booleans,
fillets, plane intersections). Bottles, rings and turned parts suit that well; free-form sculpted shapes do not yet.

---

## 1. Pipeline at a glance

```
ref photos ──► measure (pixels → units) ──► keel model (B-rep) ──► meshes with exact normals
                                                                      │
              fit cameras to photos (silhouette / landmarks) ◄────────┤
                                                                      ▼
              clay render (neutral, opaque) ──► GATE: shape matches?
                                                                      ▼
              optical/material render (LuxCore) ──► compare sheets ──► review ──► iterate
```

| Stage | Tool | Example script |
|---|---|---|
| Geometry | keel (B-rep CAD as Python code) | `model.py` |
| Label/print textures | PIL from photo crops | `make_label.py` |
| Logo / emblem | parametric curves fitted on a photo crop | `emblem.py` (+ `emblem_check.png`) |
| Cameras | silhouette IoU fit + landmark fit | `fit_poses.py`, `fit_neck.py` → `poses.json` |
| Section check | model sections drawn over photos | `section_overlay.py` → `sections.png` |
| Preview render | Cycles on the GPU (seconds per view) | a Cycles preview script |
| Final render | LuxCoreRender (pyluxcore, OptiX) | `render_lux.py`, `render_all.sh` |
| Scene layout | Blender as a viewer/editor, round trip to the final renderer | `make_blend.py`, `read_layout.py` |
| Review sheets | photo vs render, matched component crops | `make_review.py` |
| Archive | per-iteration copy + manifest | `archive/iterN/` |

---

## 2. Process rules (learned the hard way)

1. **Name references by view**: `ref_front.png`, `ref_three_quarter.png`, … and renders `lux_<view>.png`,
   `clay_<view>.png`. Every comparison sheet pairs `ref_<v>` with `<prefix>_<v>`.
2. **Use ALL reference photos for every decision.** One view lies: a front photo can't tell a square base from a
   pinched one; a top view's wavy outline was refraction, not shape.
3. **Never encode an optical effect as geometry.** The bottle's "pinched" top outline and "waisted" front were
   refraction; the actual fix was a straight-sided exterior plus an inward-bowed *cavity*. Confirm with a clay render
   before changing shape.
4. **Clay first, glass later.** Render every view with all materials opaque matte grey (`clay=1`). Shape errors are
   obvious there and invisible through glass.
5. **Section overlays turn opinions into numbers.** Cut the model at y=0 and draw it over the front photo (scaled to
   the measured body width, base on the measured baseline). Wall thickness, floor height, cap height and shoulder
   rise become measurable.
6. **Fit the cameras before judging proportions.** Mismatched elevation was mistaken for a short sleeve and a tall
   neck. Fix the camera, then re-judge.
7. **Change one thing, A/B it, keep or revert.** e.g. smooth vs ribbed cavity rendered side by side proved the ribs
   caused the "teeth"; dispersion 0 vs 0.0042 proved fringes weren't from dispersion.
8. **Diagnose by elimination.** When something is wrong (blown label), toggle one light/feature at a time
   (`off=key`, `noglass=1`, `hdri=0`) and measure pixel values. That found the HDRI as the culprit in one pass.
9. **Measure, don't eyeball.** Sample photo pixels (colour, edges) with numpy. Every number in the model should trace
   back to a measurement or a stated assumption, and say so in a comment.
10. **Archive before each iteration** (renders, meshes, scripts, keel revision, script hashes): review documents link
    to files that get overwritten.
11. **Fast renderer until the geometry is right.** Geometry rounds use a preview renderer that takes seconds per view
    (Cycles on the GPU); the slow, physically richer renderer is for the look once the shape has passed.
12. **Evaluation is external; the plan drives the work.** Each iteration is defined by `iteration_N_plan.md`, written
    from an external review. The modeller executes the plan and delivers renders. It does not grade its own results:
    judging fidelity is the external reviewer's job, and their next review starts the next iteration (section 8).

---

## 3. Measuring from photos

| Need | Technique |
|---|---|
| Scale | Pick one known/assumed dimension (body width), derive all others as ratios. Fix overall scale from a physical constraint (here: brim-full volume ≈ 110 ml for a 100 ml product). |
| Edges / extents | Saturation mask (`max−min` of RGB) for coloured liquid; diff-from-backdrop for silhouettes; scan rows/columns for first/last hit. |
| Gridded crops | Draw a 50/250 px grid on the photo and crop the region; read coordinates by eye when automatic edges are confused by reflections. |
| Colour of a medium | Sample a patch *at the same physical location* in photo and render (find it by a profile down the centre column, not fixed pixel boxes; framing differs). |
| Logo/emblem | Isolate the part (dark cap = filled threshold), crop to its own bbox, normalise units to it. Automatic skeleton tracing of thin highlight contours was too noisy; **parametric curves (ellipses, 3-point arcs, circles) fitted by overlaying them on the crop** worked and are clean, symmetric and editable. |
| Typography | Lift the ink straight from a rectified, near-orthographic photo crop (soft threshold → alpha). Exact letterforms, weight, tracking; beats any substitute font. Zero out crop edges (glass rims leak in). |
| Facet count | Count on the top view; the reviewer corrected 10 → 12 because this was skipped. |
| Scale from a repeated feature | When no dimension is known, use the spacing of a repeated feature (stone pitch, rib pitch) as the ruler, and check it against a second one. The ring was first built at half size from a mis-read pixel scale (83 px/mm instead of ~40). |

---

## 4. keel modelling: patterns and gotchas

**Patterns that worked**
- Outer body: `outline.to_sketch().extrude(H)` from true arcs (`ThreePointArc`, `Polyline`), not polygon-sampled
  curves (faceted outlines break fillets).
- Rectangle-to-circle shoulder: a **revolved cosine profile** (flat under the cap, tangent to the body top). A keel
  `loft` (rounded square → circle) also worked; keep it as an alternative.
- Inner cavity built **independently** of the outside (own wall thicknesses, waist, floor, roof), not an inset copy.
- Bowed walls: intersect the cavity with a "waist block" (a box with four big cylinders subtracted).
- Ribs that follow a bowed wall: **torus sections concentric with the bow**, so they fade out on their own; straight
  ribs grazed the curved wall and broke the boolean.
- Turned/stepped metal parts: **one revolved profile polygon** with explicit steps, grooves and bevels instead of
  stacked cylinders.
- Engraving: per-piece cutting tools from polygons, with tapered extrude for sloped walls (`taper=-flank`); cut **one
  piece at a time** and check volume dropped.
- Round recessed insert/outlet: radial cylinders (recess, seated disc, orifice) rotated to face the camera.

**Gotchas (each cost a rebuild)**
| Symptom | Cause | Fix |
|---|---|---|
| `fuse/cut failed: impossible result` | coincident faces | make tools 0.5–1 mm proud; let one tool alone define a face (e.g. extend the prism past the roof box) |
| Boolean fails with ribs / domes | tangent or near-coplanar surfaces (0.8 mm dome on a huge sphere; rib tangent to bowed wall) | skip features below a threshold; make features concentric with the surface they sit on |
| Intersect fails, swap works | operation order matters | e.g. waist intersect first, then subtract ribs |
| Fillet fails on full edge loop | multi-loop fillets | fillet `faces(">Z")[0].edges()` one loop at a time; radius < adjacent arc radius (6 mm fillet on a 6 mm corner arc fails) |
| Helix fails (> ~40 turns) | kernel limit | stack helix segments |
| Engraving silently missing | **clockwise outline extrudes downward** into the part | force counter-clockwise loops before extruding |
| Merged tools drop pieces | unioned overlapping flared tools | return a list, cut one by one, verify volume |
| Tapered extrude fails on complex outline | draft sweep limit | fall back to straight walls for that piece (report it) |
| Polygon with duplicate point | arc end == next side start | drop the duplicate |
| STEP export fails ("internal voids") | known keel limitation | keep STL/USD; log which part |
| Multi-part USD loses names | keel `export([...], usda)` bug | export each part, splice with `usd_merge.py` |

Always print `is_valid`, volume and bbox per part after a build.

---

## 5. Meshes for rendering

- Tessellate from the B-rep with **tight tolerances** (chord 0.005, angle 2°) and export the **B-rep's exact normals**.
- **Split normals at creases** (angle between vertex normal and face normal > ~8°), or facets (cap) get smoothed.
- Verify winding vs normals agree and signed volume is positive (outward).
- For nested dielectrics keep the **glass as a closed solid** (`glass_full`) and the liquid as its own closed solid
  pushed ~0.03 mm into the glass; the renderer's volume priorities resolve the shared interface.

---

## 6. Rendering transparent / thick-glass objects

**Cycles vs LuxCore.** Cycles got the shape right but thick glass looked flat: weak caustics, no dispersion, pale
gold. LuxCoreRender (path tracing + hybrid back/forward light tracing, volume priorities, Cauchy dispersion) was
clearly closer. Use LuxCore for glass/liquid hero shots.

**LuxCore setup**
- `pyluxcore` (2.11) in its own Python environment. Point `LD_LIBRARY_PATH` at a recent CUDA NVRTC (e.g. the
  pip `nvidia-cuda-nvrtc` package, with a `libnvrtc.so` link): an older system NVRTC makes GPU kernel compilation
  fail ("unrecognized option --pch"). If OptiX fails to compile, plain CUDA still works (slower).
- Property quirks: numpy scalars → `std::bad_cast` (cast to Python float/int); a volume named like its material breaks
  parsing; parse per entity to get readable errors; image-map filter values are lowercase; emission is **one-sided**
  (wind emitters toward the subject); FOV spans the long image side; float film buffer is **bottom-up**; end scripts
  with `os._exit(0)` after flushing (teardown crashes).

**Materials**
- Glass: `glass`, IOR 1.52 volume, tiny absorption, dispersion `cauchyb` ~0.002 (subtle).
- Liquid: `glass` material + `clear` volume, IOR 1.36, **higher priority than glass**; absorption **calibrated from
  the photo**: σ = −ln(T)/L per channel, T = photo colour / backdrop (linear), L = modelled path length. One setting
  for all views; a fudge factor tuned on one view turned other views orange.
- Air pocket in the neck: stop the liquid below the neck, or a gold "spacer" appears under the cap.
- Dip tube: smooth glass, IOR near the liquid, filled: nearly invisible (rough plastic drew a white line).
- Black lacquer: `glossy2`, very low kd, small ks; black comes from **dark surroundings** (black flags), not from
  killing the material.
- Polished metal: `metal2` aluminium, roughness ~0.04; needs light *and* dark cards to show its form.
- Paper: matte image map (print over ~0.84 albedo) + irregular multi-scale grain bump (no regular weave) + embossed
  border as a soft ridge in the bump map (not geometry).

**Studio**
- One dominant broad **key from camera right** → the photos' soft leftward shadow; backdrop mostly **diffuse** (a
  self-lit backdrop kills shadows).
- Vertical strip softboxes placed by mirror geometry so one cap facet carries the bright band.
- Black flags around the set; a backlit card behind the bottle (seen only through the glass).
- **Rotate the whole studio, HDRI included, with the camera**; a fixed HDRI blew out the label in the 3/4 view at
  ~10× the front's light.
- View-specific light tweaks are allowed but must be documented in code (e.g. dimmer top fill for the neck shot).

**Output and compositing**
- Render with exposure headroom (tonemap scale ~0.3); read the **unclipped float buffer**, not the PNG.
- **Clean plate**: render the empty studio + a bottle alpha mask; backdrop = render/plate × target grey (even
  backdrop, shadows/caustics preserved as ratios); bottle × same gain with a luminance highlight roll-off.
- Denoise with OIDN **guided by albedo + normal passes** (keeps emblem, grain, seams).
- Final: 1440×1800, ~300 s per view on a data-centre GPU.

---

## 7. Camera matching

- **Silhouette fit** (`fit_poses.py`): photo mask (saturation/diff from backdrop, holes filled, largest piece) vs union
  of projected **convex hulls** per part (vertex splats left holes); Nelder–Mead on 1−IoU over az/el/dist/target. IoU
  0.80–0.92 reached.
- Near-symmetric views (square top) drift in azimuth; snap to the obvious value.
- Close-ups cropped by the frame: **landmark fit** (`fit_neck.py`): ellipse centres/widths of known circles + a
  corner point + **ellipse aspect ratios** (which fix elevation); bounded least squares.
- Check label/feature placement after fitting; a mirrored solution can score nearly as well.
- **Objects with a through hole (rings)**: convex hulls fill the hole. Splat a dense sample of mesh vertices instead,
  close the gaps with a small morphological closing, and fit pose (spin about the axis, tilt, elevation, azimuth) plus
  framing (field of view, image shift). IoU 0.72–0.82; the misses were the object's reflection on the floor, which a
  colour threshold cannot separate from the object.
- **Verify the fit in the renderer, not only in the fitting code.** Project a few vertices with the renderer's own
  camera and compare them with the fit's projection. A sign error in the camera shift (Blender moves the frame, so the
  object moves the other way) put the rendered ring well off the photo while the fit itself reported IoU 0.8.
- **Floor reflections**: on a glossy sweep the reflection is as saturated as the object. Mirror the model in the floor
  and ignore pixels only the reflection covers, rather than fighting it with thresholds. Fit the camera distance too
  (it sets the perspective).
- **Rotation about a symmetry axis** (a ring's spin): after the silhouette fit, scan that angle over one period with
  quick low-res renders and score each against the photo by where plain metal (saturated) and stones (white) fall
  (normalised cross-correlation of blurred saturation maps).

---

## 8. Iteration loop: external evaluation, plan-driven execution

```
   ┌─────────────────────────── EXTERNAL ───────────────────────────┐
   │ reviewer compares ref_<v> vs lux_<v> (+ clay, components)       │
   │ → reconstruction_feedback_iteration_N.md (diagnosis, P0/P1/P2,   │
   │   acceptance checklist)                                         │
   └───────────────┬─────────────────────────────────▲──────────────┘
                   ▼                                 │ deliverables
   iteration_N_plan.md  ──defines──►  execution ─────┘ (renders, sheets, change log)
```

**Roles**
- **External evaluator** (the user or a review agent; not the modeller): compares the delivered images with the
  references, decides what is wrong and what has passed, and writes the review. Their checklist is the acceptance
  standard.
- **Modeller**: turns the review into `iteration_N_plan.md`, executes it, and delivers the outputs. It does **not**
  declare items passed or failed.

### 8.0 The feedback editor (the review instrument)

The external review is written on a **feedback editor**: a web page (one per object) that shows each reference image next to the reconstruction from the fitted camera.

```
 finals + clay ──publish──► feedback editor ──reviewer marks──► Generate feedback.md
      ▲                     (ref | render, blend slider,        (+ images/<view>_<n>.png)
      │                      final/clay toggle)                          │
      └──── execution ◄── iteration_N_plan.md ◄── modeller reads ◄──────┘
```

- **What a note holds:** a freehand mark on either image, shown on both at the same place (a closed outline round an
  area, or an open line along an edge); a severity (must / should / minor); and any of:
  - a comment;
  - pink strokes drawn on the images ("what it should look like there");
  - a sketch pad (e.g. a profile). Black and pink pens.
- **Outline only ("infer"):** a note with no text, drawing or sketch tells the modeller to find the difference
  itself by close comparison of the marked region (see 8.1).
- **Export:** `reconstruction_feedback_iteration_N_<round>_review.md` plus one picture per note (photo crop | render
  crop | sketch, with the outline and drawing on the crops). It is saved as a zip, and also stored in the page's
  database where the modeller can read it directly.
- **Rounds:** each iteration's notes are stored under their own round key, so a new round opens empty and old notes
  stay readable. A preview round (quick renders) can run before the finals; the cameras are identical, so the notes
  still apply to the finals.
- **The modeller maintains the page:** it publishes each iteration's renders to the same URL, bumps the round, and
  adds editor features the reviewer asks for.
- **Touch screens:** freehand outlines are hard with a finger. On phones the editor marks a **circle** (centre, then
  drag the radius), page scrolling is off only while a Mark toggle is on, and a resize never rebuilds the view during
  a stroke.
- **Lessons:** keep notes visual (a picture removes ambiguity; three rounds were lost on "the line" before the
  pictures existed). Crop every note region from both images before planning (`region_check.py`).

### 8.1 Read the review, write the plan

`reconstruction_feedback_iteration_N.md` → `iteration_N_plan.md`:

1. **Read the whole review before acting**: diagnosis, every section, the priority table, the recommended sequence,
   the acceptance checklist, the interpretation limits. Note what it marks as resolved; don't redo those.
2. **Map each item to the scene**: the cause in the current code (known, or a hypothesis to verify) and the concrete
   action (file, function, parameter). Reviews describe what they see, not why; don't add geometry for something that
   may be optical (rule 3).
3. **Write `iteration_N_plan.md`** next to the review:
   - Stage 0: archive (the review links point to files that will be overwritten).
   - Stages in the review's order, typically **A shape → B optics → C details → D photographic matching**. Each is a
     table `review item | current cause | action`, ending with a **technical gate** (preconditions to move on: valid
     solids, renders complete, a diagnostic run) and the **deliverables** for the evaluator.
   - Risks with fallbacks, time estimates.
4. **Get approval of the plan.** From then on **the plan defines the work**: execute what it says. Anything that comes
   up mid-way (a user correction, a bug) goes into the plan file as an amendment, so the plan stays the record of
   what was done.

**"Infer from the images" notes** (review page: an outline with no text, sketch or drawing). The reviewer marks a
region and leaves the diagnosis to the modeller. Crop the region at full resolution from the photo and the render
(`region_check.py`, or the exported picture), compare them closely (shape, edges, lines, highlights, colour, texture),
measure the difference in pixels, and write the inferred issue into the plan with that measurement. State it as an
inference, so the reviewer can correct it.

### 8.2 Execute and deliver

1. Work stage by stage. Gates are technical checks (geometry valid, clay rendered, A/B test run), not fidelity
   verdicts.
2. Render clay + finals for all views at the agreed quality.
3. `make_review.py` → `compare_photo_vs_<prefix>.png` (all views) and `components_<prefix>.png` (cap, label, base,
   emblem, atomizer, shoulder crops placed relative to each image's own bottle bbox) to support the evaluator.
4. Deliver a **change log against the plan**: each plan item done / not done / changed (and why), the files produced,
   and known open issues observed during the work. Factual, with no pass/fail claims on fidelity.
5. Archive, and wait for `reconstruction_feedback_iteration_N+1.md`.

The acceptance checklist in a review (adapt per object) typically covers: silhouette and corners; shoulder/neck
transition; cavity and floor; calm continuous liquid; no unexplained repeated optical patterns; cap finish in every
view; logo complete, placed and oriented; mechanical details (outlet, rings); label paper and typography; consistent
materials across views; grounding shadow; no clipping, noise or fringes.

## 9. Jewellery: diamonds and polished gold

**Geometry (meshes directly, no B-rep needed)**
- **Round brilliant as an exact polyhedron**: the intersection of the half-spaces of its 57 facet planes plus the
  girdle (`scipy.spatial.HalfspaceIntersection`, then a convex hull). Ideal proportions: table 57 %, crown 34.5°,
  pavilion 40.75°. Build the star and upper-girdle facets by construction (through the table edge and the star tip),
  not by guessed angles. Every facet stays flat with a true normal.
- Pavé: stones on staggered rows, girdle just below the metal surface, beads at the midpoints between neighbours;
  bezel stones in collars (a cone plus lip tori). Check every stone is a closed, outward-wound solid (signed volume).

**Diamond material.** IOR 2.417 with dispersion (LuxCore `cauchyb` ≈ 0.0136; Cycles' Principled *Dispersion* input).
Deep specular/transmission bounce limits (32+), or the total internal reflection that makes the brilliance is cut.

**Why stones look pink (or grey) instead of white.** A well-cut stone mirrors what is above it, through total
internal reflection, but it also shows whatever lies under its pavilion. If the cavity under the pavé is lit polished
gold, every stone turns pink. On the real ring that cavity is closed and unlit. Diagnosis (rule 8): render once with
the metal set to grey; if the stones turn white, the colour comes from the metal under them. Fix: give the cavity
floor a dark material.

**High-key product lighting (white "tent" photos)**
- Light mostly from the **environment**: a bright surround, brighter overhead and darker towards the horizon. The
  gold needs that gradient to show its form; a uniform surround makes it flat, and a large soft box near the object
  lights the floor but not the metal's reflections.
- An **endless cream floor**; set its albedo to the photo's backdrop colour rather than raising exposure (exposure
  clips the gold first).
- **Glint lights**: a few tiny emitters that are invisible to diffuse rays and cast no shadow, so they add sparkle to
  the metal and stones without flooding the floor or adding hard shadows. Turn caustics off in the preview: glints
  bounced off the gold show up as a glow on the floor.
- Calibrate exposure on numbers: the mean backdrop pixel in a corner, and the 10/50/90 % luminance of the metal mask,
  photo vs render.

## 10. New scenes and motion (after the match)

- **Layout in Blender, render elsewhere.** Export the render scene (meshes, materials, camera) to a `.blend` with one
  handle per part and a camera that matches the renderer's. The user moves parts and the camera and saves; a script
  reads the transforms and camera back into a layout file the final renderer applies. Composition takes minutes
  instead of a render round trip per change.
- **Build sets as plain meshes**: walls, shelves, niches lit from photo crops. A procedural prop (a blossom branch:
  tubes, cupped petals, colours sampled from a photo) beat image-to-3D meshes, which came out flat or lumpy.
- **Animation: move the camera, not the object.** Render ray-traced keyframes on a camera orbit, then let a
  first/last-frame video model (LTX) interpolate between them. **One run** with keyframes at the start, middle and end
  worked; two short segments cross-faded showed a doubled label at the joint. Keep the motion prompt short and about
  the camera only.

## 11. Time and cost reference

**Perfume bottle**
- Geometry build (keel): 20 s – 2 min per rebuild (torus ribs are the slow part).
- Clay check, 4 views: ~2 min. Finals, 4 views @ 300 s: ~25 min.
- Three review iterations, about a day of wall time; most of it was diagnosing optics and booleans, not modelling.

**Ring**
- Mesh build: seconds. Cycles previews on a data-centre GPU (OptiX): ~5 s per view at 1000×1000, 256 samples.
- Camera fit for 3 views: ~15 s on a laptop.

## 12. Checklist to start a new object

- [ ] Copy the previous object's scripts as a template; rename refs `ref_<view>.png`.
- [ ] Measure key dimensions + decide scale constraint; write them as named constants with source comments.
- [ ] Build the outer shape; clay render all views; section overlay; fix until the gate passes.
- [ ] Fit cameras (silhouette, then landmarks for close-ups); point splats, not hulls, for objects with holes.
- [ ] Iterate geometry with the fast preview renderer; switch to the final renderer once the shape passes.
- [ ] Inner/secondary shapes, mechanics, logo (parametric fit), print (photo lift).
- [ ] Materials with photo-calibrated parameters; one studio rotating with the camera.
- [ ] Finals + review sheets + change log against the plan; archive; hand over for external evaluation.
- [ ] Next iteration: read the review → write `iteration_N_plan.md` → approval → execute (section 8).
- [ ] New scenes or motion: layout round trip through Blender; orbit keyframes + one first/last-frame video run (section 10).
