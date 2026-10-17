#!/bin/bash
# camera orbit in the wall5 shop: the camera at -45, 0 and +45 degrees around the bottle (the bottle and set fixed),
# then two LTX segments of 65 frames each: left -> front -> right
export LD_LIBRARY_PATH=${LUX_NVRTC_LIB:-}
cd "$(dirname "$0")"
PY=${LUX_PYTHON:-python}
LTXD=${LTX_DIR:?set LTX_DIR=path/to/LTX-2.5-repo}/parade_flf
mkdir -p shop45
for p in orb0:front orbL:-135 orbR:-45; do
  n=${p%%:*}; a=${p#*:}
  AZ=""; [ "$a" != front ] && AZ="az=$a"
  $PY parade_lux.py view=front shop=1 $AZ lens=${LENS:-100} el=2 wall_dz=${WALL_DZ:-160} counter_d=420 branch_coat=0 aperture=0.001 res=1080x1350 time=900 out=shop45/$n.png 2>&1 | grep -E "^rendered|rejected|Error"
  $PY - "$n" <<'PYEOF'
import sys
from PIL import Image
n = sys.argv[1]
Image.open(f"shop45/{n}.png").convert("RGB").resize((768, 960), Image.LANCZOS).save(f"$LTXD/shop_{n}.jpg", quality=95)
PYEOF
done
cd "${LTX_DIR:?set LTX_DIR=path/to/LTX-2.5-repo}"
export PATH="$HOME/.local/bin:$PATH" HF_HOME=/scratch/hf
M=/scratch/ltx25_models
PROMPT="A square glass perfume bottle filled with pale golden liquid, black faceted cap, white paper label reading PARADE CELINE PARIS, vertical fluted inner glass, standing on a white marble counter in an elegant Parisian perfume boutique, a delicate cherry blossom branch lying on the counter behind it, white wall with lit display niches and perfume bottles in the background, cool soft light. The camera slowly orbits around the still bottle at constant height, with gentle parallax on the boutique shelves behind. Product packshot, photorealistic, sharp details"
seg() {
  CUDA_VISIBLE_DEVICES=1 uv run python -m ltx_pipelines.distilled \
    --transformer-path $M/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors \
    --text-encoder-path $M/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
    --video-vae-path $M/vae/ltx-2.5-video-vae-bf16.safetensors \
    --audio-vae-path $M/vae/ltx-2.5-audio-vae-bf16.safetensors \
    --spatial-upsampler-path $M/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
    --height 960 --width 768 --num-frames 65 --frame-rate 24 --seed 1 --prompt "$PROMPT" \
    --image parade_flf/shop_$1.jpg 0 1.0 --image parade_flf/shop_$2.jpg 64 1.0 --output-path parade_flf/$3.mp4 2>&1 | tail -1
}
seg orbL orb0 parade_flf_orbit_seg1
seg orb0 orbR parade_flf_orbit_seg2
echo ORBITDONE
