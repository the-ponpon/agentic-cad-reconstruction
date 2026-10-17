# Feedback editor

A single-page tool: each reference photo next to the render from the same fitted camera (side by side, or blended
with a slider), where the reviewer marks regions (freehand, or a circle by finger on phones), sets a severity, adds a
comment or a sketch, and exports `reconstruction_feedback_iteration_N_<round>_review.md` plus one picture per note.

This copy is set up for the perfume's four views. Edit `VIEWS`, `ITER`, `ROUND` and the titles at the top of the script, and put
`img/ref_<view>.jpg` and `img/lux_<view>.jpg` next to it. It was published as a Claude artifact (notes stored in the
artifact's database); opened as a plain file it falls back to saving notes in the browser.
