# Working on a reconstruction in this repo (instructions for Claude Code)

You rebuild a real object from a few reference photos as exact geometry, render it with physical light simulation,
and iterate with a human reviewer until the renders match the photos. Read `PLAYBOOK.md` before starting: it is the
method. `perfume/` is the worked example to copy from.

## The loop

1. **References.** Photos go in `<object>/refs/` (or the object folder), one per view, named `ref_<view>.png`.
   Never commit photos of branded products.
2. **Inspect at native resolution.** Before modelling any part, look at the photos (close-ups above all) in
   full-resolution tiles of about 1000 px, never only on downscaled sheets, and write `<object>/detail_inventory.md`:
   per part, what the photo shows, what the model has, what to build (counts, edges, small separate parts, prints,
   finishes). Compare every render against the same native crops.
3. **Measure.** Read sizes off the photos with numpy (edges, masks, pixel scans), never by eye alone. Fix the scale
   from one known or physical constraint (capacity, a published dimension, a repeated feature's pitch). Write every
   size as a named constant with a comment saying where it was measured.
4. **Model.** Write the geometry as code: keel (B-rep) for CAD-like parts (`perfume/parade.py` is the template),
   or plain meshes / implicit solids when that suits the shape better. Print validity, volume and bounding box
   after each build.
5. **Cameras.** Fit one camera per photo (`perfume/fit_poses.py`: silhouette overlap; `perfume/fit_neck.py`:
   landmarks for close-ups). Check every fit by rendering the model with the renderer's own camera and overlaying
   it on the photo: the fitting code and the renderer must agree (sign of the shift, roll, lens).
6. **Clay first.** Render opaque grey from every fitted camera and compare shapes before any material work
   (`perfume/section_overlay.py` draws model sections over the photos).
7. **Materials and light.** LuxCore for glass and liquids (`perfume/parade_lux.py`), Cycles for fast previews.
   Calibrate colours and absorption on measured photo pixels, one setting for all views.
8. **Review.** Publish photo / render pairs on the feedback page (`tools/review_page/`); the human marks what is
   wrong and exports `reconstruction_feedback_iteration_N_<round>_review.md` with one picture per note.
9. **Plan, then execute.** Turn each review into `<object>/iteration_N_plan.md`: every note mapped to its cause in
   the code and a concrete change, stages with a technical gate each, deliverables. Get the plan approved, then
   follow it. Notes with no text ("infer") mean: crop the marked region in both images and find the difference
   yourself; state what you inferred.
10. **Deliver** renders for every view, comparison sheets (`perfume/make_review.py`), and a change log against the
   plan. Do not grade your own fidelity: the reviewer does.

## Rules that save rebuilds

- Use all the photos for every decision; one view lies.
- Never encode an optical effect (refraction, reflection) as geometry: confirm on a clay render first.
- Change one thing at a time and A/B it; diagnose by switching one light or feature off at a time.
- Archive renders, meshes and scripts before each iteration (`<object>/archive/iterN/`).
- Long renders run in the background on the GPU host; poll them, do not block on them.

## Environment

Remote rendering is configured by environment variables: `RENDER_HOST`, `SSH_KEY`, `REMOTE_DIR`, `LUX_PYTHON`,
`LUX_NVRTC_LIB`, `BLENDER`, `LTX_DIR`. keel (https://github.com/amywork777/keel) runs `perfume/parade.py`.
