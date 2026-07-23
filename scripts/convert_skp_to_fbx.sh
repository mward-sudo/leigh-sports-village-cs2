#!/usr/bin/env bash
# Re-convert LSV stadium.skp → CS2-ready FBX
# Pipeline: openskp GLB (mm) → Blender mm→m, −90°X + ×100 bake → FBX
set -euo pipefail

ROOT="/Users/michael/Developer/cities skylines 2 mods/Leigh Sports Village Large Park Asset"
SKP="${1:-/Users/michael/Downloads/LSV stadium.skp}"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

if [[ ! -f "$SKP" ]]; then
  echo "SKP not found: $SKP" >&2
  exit 1
fi

python3 -c "import openskp, scipy" 2>/dev/null || pip3 install openskp scipy

python3 << PY
from openskp import SkpFile
from openskp.export import glb
import os

out = "$ROOT/source"
os.makedirs(out, exist_ok=True)
skp = SkpFile.open("$SKP")
glb.export(skp, os.path.join(out, "LSV_stadium.glb"))
print("GLB written")
PY

"$BLENDER" --background --python "$ROOT/scripts/blender_export_fbx.py"

magick "$ROOT/.tmp/skp_extract/materials/_1/pitch4.JPG" \
  -resize 1024x1024^ -gravity center -extent 1024x1024 \
  "$ROOT/art_project/LeighSportsVillage/LSV_Stadium/NA_LSVStadium_Base_BaseColorMap.png" 2>/dev/null || true

echo "Done. Import folder: $ROOT/art_project/LeighSportsVillage/LSV_Stadium"
