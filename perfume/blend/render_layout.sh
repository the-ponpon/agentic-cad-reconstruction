#!/bin/bash
# LuxCore render of a layout edited in Blender:
#   blend/render_layout.sh [file.blend] [quick|final]   ->  blend/<file>_<mode>.png
# quick: 540x675, 60 s (about 1.5 min with setup) / final: 1080x1350, 900 s
set -e
cd "$(dirname "$0")"
B=${1:-parade_shop_layout.blend}; MODE=${2:-quick}; STEM=$(basename "$B" .blend)
: "${RENDER_HOST:?set RENDER_HOST=user@gpu-host}"; KEY=${SSH_KEY:-~/.ssh/id_ed25519}; BOX=$RENDER_HOST; R=${REMOTE_DIR:-dev/keel/anim/parade}
${BLENDER:-blender} --background "$B" --python read_layout.py -- "$STEM.layout.json" 2>&1 | grep wrote
scp -q -i $KEY "$STEM.layout.json" $BOX:$R/shop/
if [ "$MODE" = final ]; then RES=1080x1350; T=900; else RES=540x675; T=60; fi
ssh -i $KEY $BOX "cd $R && export LD_LIBRARY_PATH=\${LUX_NVRTC_LIB:-}; \
  \${LUX_PYTHON:-python} parade_lux.py view=front shop=1 lens=100 el=2 wall_dz=160 counter_d=420 aperture=0.001 \
  res=$RES time=$T layout=shop/$STEM.layout.json out=shop/${STEM}_$MODE.png 2>&1 | grep -E 'layout:|rejected|Error'"
scp -q -i $KEY $BOX:$R/shop/${STEM}_$MODE.png .
echo "-> blend/${STEM}_$MODE.png"
