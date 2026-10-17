# agentic-cad-reconstruction

**Photos → CAD → photoreal render**, with an AI agent doing the modelling and a human reviewing.

Scripts and method from an exploration: rebuilding real products from a handful of reference photos as exact
geometry, with an AI agent (Claude) writing the model, physical light simulation checking it against the photos,
and a human reviewing each round. The worked example:

- **`perfume/`**: a thick-glass perfume bottle full of liquid, modelled as B-rep CAD (keel), rendered with
  LuxCoreRender (nested dielectrics, measured absorption, dispersion), cameras fitted to each photo, plus the
  cutaway, a Blender layout round trip, and a camera-orbit animation with a video model between ray-traced keys.

The method itself (what worked, what didn't, the review loop) is in **[PLAYBOOK.md](PLAYBOOK.md)**: read it first.

## What this is, and isn't

- These are working scripts from an exploration, not a library. They are readable and commented, with the
  measured values and the reasoning left in, but they assume the layout described below and you'll adapt paths.
- **No reference photos are included**: they belong to the brands. `refs/README.md` says what to shoot or collect,
  and how to name it. The cap emblem in `perfume/emblem.py` is a placeholder for the same reason (the original was
  traced from the photo with `trace_emblem.py`).
- `perfume/parade.py` is written for **[keel](https://github.com/amywork777/keel)**, a small Python CAD language on
  NVIDIA's usd-brep kernel (exact B-rep, USD output). Run it with keel's `bin/keel perfume/parade.py`; it writes the
  meshes (`mesh/*.npz`, exact B-rep normals) that the rendering scripts use.
  keel is a third-party project, not mine: it is not part of this repository, and its repo states no licence at the
  time of writing, so check its terms before reusing its code. This repository's MIT licence covers only the files here.
- Trademarks mentioned in comments belong to their owners; this is a technical exercise with no affiliation.

## Layout

| Folder | What | Main scripts |
|---|---|---|
| `perfume/` | model, cameras, render, review | `parade.py` (model), `fit_poses.py` + `fit_neck.py` (cameras), `section_overlay.py` (shape gate), `parade_lux.py` (LuxCore), `make_review.py` + `region_check.py` (review sheets), `cut_meshes.py` + `cutaway.py` (cutaway) |
| `perfume/blend/` | edit the scene in Blender, render in LuxCore | `make_blend.py`, `read_layout.py`, `render_layout.sh` |
| `perfume/` (motion) | orbit keys + video model | `orbit_segs.sh`, `orbit_ltx_3k.sh` |
| `tools/review_page/` | the feedback editor (photo vs render, marks, notes, export) | `index.html` |

## Requirements

- Python 3.10+, `numpy scipy pillow scikit-image matplotlib` (see `requirements.txt`)
- Blender 4.2+ (its `bpy` as a module or the app) for the Cycles previews and the layout round trip
- LuxCoreRender's Python module (`pyluxcore`) for the glass renders; a CUDA GPU helps a lot
- [keel](https://github.com/amywork777/keel) for `perfume/parade.py` only (native build on macOS, or Docker / `pip install usd-brep` on Linux)
- Optional: an LTX video model checkout for the orbit animation (`LTX_DIR`)

Remote rendering settings are environment variables: `RENDER_HOST`, `SSH_KEY`, `REMOTE_DIR`, `LUX_PYTHON`,
`LUX_NVRTC_LIB`, `BLENDER`, `LTX_DIR`.

## Licence

MIT, see `LICENSE`.
