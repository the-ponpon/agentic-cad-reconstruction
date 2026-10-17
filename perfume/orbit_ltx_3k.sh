#!/bin/bash
# the orbit as one 121-frame LTX run with the three keyframes at 0 / 60 / 120 (two short 65-frame segments cross-faded)
cd "${LTX_DIR:?set LTX_DIR=path/to/LTX-2.5-repo}"
export PATH="$HOME/.local/bin:$PATH" HF_HOME=/scratch/hf
M=/scratch/ltx25_models
PROMPT="Smooth orbit shot: the camera arcs sideways around a glass perfume bottle standing still on a marble counter."
seg() {
  CUDA_VISIBLE_DEVICES=1 uv run python -m ltx_pipelines.distilled \
    --transformer-path $M/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors \
    --text-encoder-path $M/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
    --video-vae-path $M/vae/ltx-2.5-video-vae-bf16.safetensors \
    --audio-vae-path $M/vae/ltx-2.5-audio-vae-bf16.safetensors \
    --spatial-upsampler-path $M/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
    --height 960 --width 768 --num-frames 121 --frame-rate 24 --seed 1 --prompt "$PROMPT" \
    --image parade_flf/shop_orbL.jpg 0 1.0 --image parade_flf/shop_orb0.jpg 60 1.0 --image parade_flf/shop_orbR.jpg 120 1.0 --output-path parade_flf/parade_flf_orbit3k.mp4 2>&1 | tail -1
}
seg
echo ORBIT3KDONE
