# Working on a reconstruction in this repo (instructions for AI coding agents)

You rebuild a real object from a few reference photos as exact geometry, render it with physical light simulation,
and iterate with a human reviewer until the renders match the photos. Read `PLAYBOOK.md` before starting: it is the
method. `perfume/` is the worked example to copy from.

Reference photos live in the object's own folder, one per view, named `ref_<view>.png` (for example
`mybottle/ref_front.png`): the scripts run from that folder and open `ref_<view>.png` there. Never commit photos of
branded products.

## First session: onboard the person

When someone opens the repo for the first time or asks for help with a new object, guide them before modelling
anything. Do these in order, and say what you are doing at each step.

1. **The object.** Ask what it is, and whether it is opaque (metal, plastic, wood, ceramic) or transparent (glass,
   liquid, gems). The answer decides the renderer and how much setup is needed.
2. **One known size.** Ask for one real dimension: a published height or width, a capacity in ml, a standard part
   (a 31.8 mm bar clamp, a coin in the shot). Without it the model has the right shape but no scale. If they have
   none, say so plainly and agree on an assumed size.
3. **The photos.** Find them (ask where they are if needed) and move or copy them into `<object>/ref_<view>.png`.
   Check each one and report:
   - how many views there are and which sides they cover (front, side, three-quarter, top, close-ups);
   - resolution: inspect at native size, ideally 1500 px or more on the object;
   - background: plain backdrops work best; busy ones need masks;
   - whether a needed view is missing (for example nothing shows the back, or no close-up of a small part).
   Three to six photos of a simple object are enough to start; more views and close-ups help for detailed parts.
4. **Setup check.** Check what is installed and help install what is missing, explaining what each piece is for:
   - Python 3.10+ and `pip install -r requirements.txt`.
   - Blender 4.2+: Cycles previews (opaque objects can be finished with Cycles alone).
   - LuxCoreRender (`pyluxcore`): only for glass, liquids and gems.
   - keel (https://github.com/amywork777/keel): only for B-rep CAD models like `perfume/parade.py`; plain meshes
     need nothing extra. keel is a third-party project: point to its own install instructions.
   - A GPU: optional. Renders run on a CUDA machine much faster; a remote one is set up with the environment
     variables below.
   Do not install anything system-wide without asking.
5. **Plan the first round.** Propose the folder (`<object>/`), which parts you will model as B-rep or as meshes, and
   which renderer you will use. Then start the loop below with steps 2 (inspection) and 5 (cameras).
6. **The review page.** Before the first review, copy `tools/review_page/` into `<object>/review/`, set its `VIEWS`,
   `ITER`, `ROUND` and titles for this object, and put `img/ref_<view>.jpg` and `img/<render>_<view>.jpg` next to it.
   Tell the person how to open it (in a browser as a local file, or published as a page if your environment can),
   how to mark what is wrong, and that *Generate feedback.md* exports the review they give back to you.

Set expectations once, briefly: each round is model → render → human review → plan → fix. The perfume bottle took
about ten rounds. The person judges fidelity, not you.

## The loop

1. **References.** One photo per view in the object folder, `ref_<view>.png`.
2. **Inspect at native resolution.** Before modelling any part, look at the photos (close-ups above all) in
   full-resolution tiles of about 1000 px, never only on downscaled sheets, and write `<object>/detail_inventory.md`:
   per part, what the photo shows, what the model has, what to build (counts, edges, small separate parts, prints,
   finishes). Compare every render against the same native crops.
3. **Measure.** Read sizes off the photos with numpy (edges, masks, pixel scans), never by eye alone. Fix the scale
   from the known dimension (or a physical constraint: capacity, a repeated feature's pitch). Write every size as a
   named constant with a comment saying where it was measured.
4. **Model.** Write the geometry as code: keel (B-rep) for CAD-like parts (`perfume/parade.py` is the template),
   or plain meshes / implicit solids when that suits the shape better. Print validity, volume and bounding box
   after each build.
5. **Cameras.** Fit one camera per photo (`perfume/fit_poses.py`: silhouette overlap; `perfume/fit_neck.py`:
   landmarks for close-ups). Check every fit by rendering the model with the renderer's own camera and overlaying
   it on the photo: the fitting code and the renderer must agree (sign of the shift, roll, lens).
6. **Clay first.** Render opaque grey from every fitted camera and compare shapes before any material work
   (`perfume/section_overlay.py` draws model sections over the photos).
7. **Materials and light.** LuxCore for glass and liquids (`perfume/parade_lux.py`), Cycles for fast previews and
   opaque objects. Calibrate colours and absorption on measured photo pixels, one setting for all views.
8. **Review.** Publish photo / render pairs on the feedback page (`<object>/review/`); the human marks what is
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
