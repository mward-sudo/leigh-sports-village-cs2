#!/usr/bin/env bash
# Re-convert LSV stadium.skp → CS2-ready textured FBX
# Pipeline:
#   1. openskp GLB (mm, face colours)
#   2. bake_sketchup_atlas.py → textured GLB + BaseColor/Normal/Mask maps
#   3. Blender mm→m, −90°X + ×100 bake → FBX
set -euo pipefail

ROOT="/Users/michael/Developer/cities skylines 2 mods/Leigh Sports Village Large Park Asset"
SKP="${1:-/Users/michael/Downloads/LSV stadium.skp}"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

if [[ ! -f "$SKP" ]]; then
  echo "SKP not found: $SKP" >&2
  exit 1
fi

python3 -c "import openskp, scipy, PIL, trimesh, numpy" 2>/dev/null || pip3 install openskp scipy pillow trimesh numpy

# Extract embedded SketchUp materials/textures (for atlas bake)
python3 << PY
import zipfile, shutil
from pathlib import Path

skp = Path("$SKP")
out = Path("$ROOT/.tmp/skp_extract")
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
with zipfile.ZipFile(skp, "r") as z:
    # SKP is a ZIP; materials live under materials/
    for name in z.namelist():
        if name.startswith("materials/") or name.startswith("meta/") or name.startswith("ref/") \
           or name in ("model.dat",) or name.startswith("thumbnails/") or name.startswith("styles/"):
            z.extract(name, out)
print("Extracted SKP materials →", out)
PY

# Intermediate GLB (geometry + metadata; colours used by bake via openskp internals)
python3 << PY
from openskp import SkpFile
from openskp.export import glb
import os

out = "$ROOT/source"
os.makedirs(out, exist_ok=True)
skp = SkpFile.open("$SKP")
skp.parse()
glb.export(skp, os.path.join(out, "LSV_stadium.glb"))
print("GLB written")
PY

# Atlas bake: SketchUp colours + key textures → BaseColorMap / Normal / Mask + textured GLB
python3 "$ROOT/scripts/bake_sketchup_atlas.py" "$SKP"

# CS2 FBX bake in Blender
"$BLENDER" --background --python "$ROOT/scripts/blender_export_fbx.py"

# Keep .tmp copy of blender script in sync for older docs/paths
cp "$ROOT/scripts/blender_export_fbx.py" "$ROOT/.tmp/blender_export_fbx.py"

echo "Done. Import folder: $ROOT/art_project/LeighSportsVillage/LSV_Stadium"
ls -la "$ROOT/art_project/LeighSportsVillage/LSV_Stadium"
