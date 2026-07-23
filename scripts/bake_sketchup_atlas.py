"""Bake SketchUp face colours + key textures into a CS2 BaseColorMap atlas.

OpenSKP's GLB keeps solid face colours but:
  - unpainted faces inherit Layer0's UI red (255,84,84) — wrong for the pitch
  - texture images are not UV-mapped into the GLB

This script captures the pre-export trimesh scene, remaps Layer0, projects
textures for known materials (pitch, seats, cladding, …), packs a 2048 atlas,
and writes a textured GLB for Blender + CS2 map PNGs.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh
from openskp import SkpFile
from openskp import _core
from PIL import Image
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals

ROOT = Path(__file__).resolve().parents[1]
SKP_DEFAULT = Path.home() / "Downloads" / "LSV stadium.skp"
MATERIALS_DIR = ROOT / ".tmp" / "skp_extract" / "materials"
OUT_DIR = ROOT / "art_project" / "LeighSportsVillage" / "LSV_Stadium"
SOURCE_DIR = ROOT / "source"
TMP_DIR = ROOT / ".tmp" / "color_bake"

ATLAS_SIZE = 2048
LAYER0 = (255, 84, 84, 255)
PITCH_FALLBACK = (123, 156, 81, 255)  # *1
DEFAULT_FILL = (190, 190, 188, 255)  # neutral concrete for leftover Layer0

# material_id_to_name / folder → texture filename under materials/
TEXTURE_BY_MAT = {
    "_1": "pitch4.JPG",
    "*1": "pitch4.JPG",
    "_71": "chair2.jpg",
    "*71": "chair2.jpg",
    "_15": "techo estadio1.jpg",
    "*15": "techo estadio1.jpg",
    "_3": "concerete.jpg",
    "*3": "concerete.jpg",
    "_4": "sides2.JPG",
    "*4": "sides2.JPG",
    "_11": "tochos.jpg",
    "*11": "tochos.jpg",
    "_117": "8.JPG",
    "*117": "8.JPG",
    "_8": "baranda estadio azul.png",
    "*8": "baranda estadio azul.png",
    "_9": "escalera con amarillo.jpg",
    "*9": "escalera con amarillo.jpg",
    "[Cladding_Stucco_White]": "Cladding_Stucco_White.jpg",
    "[Concrete_Aggregate_Smoke]": "Concrete_Aggregate_Smoke.jpg",
    "[Concrete_Aggregate_Smoke]1": "Concrete_Aggregate_Smoke.jpg",
    "[Concrete_Aggregate_Smoke]2": "Concrete_Aggregate_Smoke.jpg",
    "[Concrete_Aggregate_Smoke]3": "Concrete_Aggregate_Smoke.jpg",
    "[Metal_Rough]1": "Metal_Rough.jpg",
    "[Metal_Rough]2": "Metal_Rough.jpg",
    "[Metal_Seamed]": "Metal_Seamed.jpg",
    "[Metal_Panel]": "Metal_Panel.jpg",
    "[Metal_Steel_Textured_White]": "Metal_Steel_Textured_White.jpg",
    "[Carpet_Plush_Charcoal]": "Carpet_Plush_Charcoal.jpg",
    "[Carpet_Plush_Charcoal]1": "Carpet_Plush_Charcoal.jpg",
    "[Fencing_Railing_Metal2]": "Fencing_Railing_Metal2.png",
    "[Vegetation_Grass1]": "Vegetation_Grass1.jpg",
    "light vert": "window.jpg",
}

# World-metres scale for texture projection (openskp mesh is mm)
TEX_SCALE_M = {
    "pitch4.JPG": 0.08,  # ~8 cm/px feel for pitch markings
    "chair2.jpg": 0.15,
    "techo estadio1.jpg": 0.25,
    "concerete.jpg": 0.20,
    "sides2.JPG": 0.20,
    "tochos.jpg": 0.15,
    "8.JPG": 0.20,
    "Cladding_Stucco_White.jpg": 0.25,
    "Concrete_Aggregate_Smoke.jpg": 0.25,
    "Metal_Rough.jpg": 0.30,
    "Metal_Seamed.jpg": 0.30,
    "Metal_Panel.jpg": 0.30,
    "Metal_Steel_Textured_White.jpg": 0.30,
    "Carpet_Plush_Charcoal.jpg": 0.20,
    "Fencing_Railing_Metal2.png": 0.15,
    "Vegetation_Grass1.jpg": 0.15,
    "baranda estadio azul.png": 0.20,
    "escalera con amarillo.jpg": 0.15,
    "window.jpg": 0.25,
}


def next_pow2(x: int) -> int:
    return 1 << int(math.ceil(math.log2(max(x, 1))))


def capture_scene(skp_path: Path):
    skp = SkpFile.open(str(skp_path))
    skp.parse()
    parsed = skp._parsed
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    holder: dict = {}
    orig = trimesh.Scene.export

    def fake_export(self, *a, **k):
        holder["scene"] = self
        path = a[0] if a else k.get("file_obj")
        if path:
            Path(path).write_bytes(b"")
        return path

    trimesh.Scene.export = fake_export
    try:
        _core.build_scene(parsed, str(TMP_DIR), "LSV_capture")
    finally:
        trimesh.Scene.export = orig

    if "scene" not in holder:
        raise RuntimeError("Failed to capture openskp scene")
    return holder["scene"], parsed


def find_texture(mat_name: str) -> Path | None:
    if not mat_name:
        return None
    fname = TEXTURE_BY_MAT.get(mat_name)
    if not fname:
        return None
    # Prefer folder matching mat_name / mapped key
    candidates = []
    for key, tex in TEXTURE_BY_MAT.items():
        if tex != fname:
            continue
        folder = MATERIALS_DIR / key
        if folder.is_dir():
            p = folder / fname
            if p.is_file():
                return p
            # case-insensitive
            for f in folder.iterdir():
                if f.name.lower() == fname.lower():
                    return f
    # brute search
    for folder in MATERIALS_DIR.iterdir():
        if not folder.is_dir():
            continue
        for f in folder.iterdir():
            if f.name.lower() == fname.lower():
                return f
    return None


def color_key(c) -> tuple:
    return (int(c[0]), int(c[1]), int(c[2]), int(c[3]) if len(c) > 3 else 255)


def remap_layer0_and_tag_pitch(mesh: trimesh.Trimesh) -> np.ndarray:
    """Return per-face tags: None | 'pitch' | texture filename.

    Also mutates face_colors: Layer0 red → pitch green or neutral fill.
    """
    fc = np.asarray(mesh.visual.face_colors).copy()
    n = mesh.face_normals
    areas = mesh.area_faces
    centroids = mesh.triangles_center

    layer0 = (
        (fc[:, 0] == LAYER0[0])
        & (fc[:, 1] == LAYER0[1])
        & (fc[:, 2] == LAYER0[2])
    )
    horiz = np.abs(n[:, 1]) > 0.85
    y = centroids[:, 1]
    y_min = float(y.min())
    # Pitch: large horizontal Layer0 near ground (within 2 m of lowest point)
    near_ground = y <= (y_min + 2000.0)  # mm
    pitch_mask = layer0 & horiz & near_ground

    # If pitch_mask is tiny, fall back to largest contiguous-ish horiz Layer0 band
    if areas[pitch_mask].sum() < 0.05 * areas.sum():
        # take lowest 15% of horizontal Layer0 by centroid y
        candidates = np.where(layer0 & horiz)[0]
        if len(candidates):
            ys = y[candidates]
            cutoff = np.percentile(ys, 15)
            pitch_mask = np.zeros(len(fc), dtype=bool)
            pitch_mask[candidates[ys <= cutoff]] = True

    tags = np.array([None] * len(fc), dtype=object)
    tags[pitch_mask] = "pitch4.JPG"
    fc[pitch_mask] = PITCH_FALLBACK

    other_layer0 = layer0 & ~pitch_mask
    fc[other_layer0] = DEFAULT_FILL

    mesh.visual.face_colors = fc
    return tags


def tag_textured_materials(mesh: trimesh.Trimesh, parsed, tags: np.ndarray) -> np.ndarray:
    """Tag faces whose solid colour matches a known textured material."""
    # Build colour → texture from materials dict
    color_to_tex: dict[tuple, str] = {}
    for mat_name, mat in parsed.get("materials", {}).items():
        c = mat["color"]
        key = (int(c["r"]), int(c["g"]), int(c["b"]), 255)
        tex = TEXTURE_BY_MAT.get(mat_name)
        if tex:
            color_to_tex[key] = tex
    for folder, mat in parsed.get("materials_by_folder", {}).items():
        c = mat["color"]
        key = (int(c["r"]), int(c["g"]), int(c["b"]), 255)
        tex = TEXTURE_BY_MAT.get(folder) or TEXTURE_BY_MAT.get(mat["name"])
        if tex:
            color_to_tex[key] = tex

    fc = np.asarray(mesh.visual.face_colors)
    for i, c in enumerate(fc):
        if tags[i] is not None:
            continue
        tex = color_to_tex.get(color_key(c))
        if tex:
            tags[i] = tex
    return tags


def explode_mesh(mesh: trimesh.Trimesh, tags: np.ndarray):
    faces = mesh.faces
    verts = mesh.vertices
    fc = np.asarray(mesh.visual.face_colors)
    new_verts = verts[faces.reshape(-1)]
    new_faces = np.arange(len(new_verts)).reshape((-1, 3))
    nm = trimesh.Trimesh(vertices=new_verts, faces=new_faces, process=False)
    nm.visual.face_colors = fc
    # tags already per-face; keep aligned
    return nm, tags


def pack_atlas(images: dict[str, Image.Image], solid_colors: list[tuple], block_solid=32):
    """Pack texture images + solid swatches into a power-of-two atlas.

    Returns (atlas_img, regions) where regions[name] = (u0,v0,u1,v1) in 0–1
    with V=0 at bottom (OpenGL / Blender).
    """
    # Resize large source textures to fit
    max_tex = 512
    items: list[tuple[str, Image.Image]] = []
    for name, img in images.items():
        im = img.convert("RGBA")
        w, h = im.size
        scale = min(1.0, max_tex / max(w, h))
        if scale < 1.0:
            im = im.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        items.append((name, im))

    for i, c in enumerate(solid_colors):
        sw = Image.new("RGBA", (block_solid, block_solid), c)
        items.append((f"solid_{i}", sw))

    # Simple shelf pack
    items.sort(key=lambda x: -x[1].size[1] * x[1].size[0])
    pad = 4
    # Estimate canvas then snap to pow2
    total_area = sum((im.size[0] + pad) * (im.size[1] + pad) for _, im in items)
    side = next_pow2(int(math.ceil(math.sqrt(total_area * 1.3))))
    side = max(side, ATLAS_SIZE)

    # Try packing; grow if needed
    while True:
        atlas = Image.new("RGBA", (side, side), (128, 128, 128, 255))
        regions = {}
        x = pad
        y = pad
        row_h = 0
        ok = True
        for name, im in items:
            w, h = im.size
            if x + w + pad > side:
                x = pad
                y += row_h + pad
                row_h = 0
            if y + h + pad > side:
                ok = False
                break
            atlas.paste(im, (x, y))
            # OpenGL V (bottom origin)
            u0 = x / side
            u1 = (x + w) / side
            v1 = 1.0 - (y / side)
            v0 = 1.0 - ((y + h) / side)
            regions[name] = (u0, v0, u1, v1, w, h, side)
            x += w + pad
            row_h = max(row_h, h)
        if ok:
            break
        side *= 2

    if side != ATLAS_SIZE:
        # Rescale to exact ATLAS_SIZE for CS2
        atlas = atlas.resize((ATLAS_SIZE, ATLAS_SIZE), Image.Resampling.NEAREST)
        scale = ATLAS_SIZE / side
        # UVs are normalized — unchanged
    return atlas, regions, solid_colors


def planar_uv_for_face(
    tri_verts_mm: np.ndarray,
    normal: np.ndarray,
    scale_m: float,
    region,
    *,
    fit_bounds: tuple[np.ndarray, np.ndarray] | None = None,
):
    """Project triangle into atlas region.

    If fit_bounds=(mins, maxs) on the two projection axes (mm), map uniquely
    across that AABB (used for the pitch so markings appear once). Otherwise
    tile by scale_m (metres per texture repeat).
    """
    u0, v0, u1, v1, _w, _h, _side = region
    an = np.abs(normal)
    axis = int(np.argmax(an))
    if axis == 0:  # YZ
        a, b = 1, 2
    elif axis == 1:  # XZ
        a, b = 0, 2
    else:  # XY
        a, b = 0, 1

    pts = tri_verts_mm[:, [a, b]]
    if fit_bounds is not None:
        mins, maxs = fit_bounds
        span = np.maximum(maxs - mins, 1e-6)
        local = (pts - mins) / span
        local = np.clip(local, 0.0, 1.0)
    else:
        local = pts * 0.001 / max(scale_m, 1e-6)
        local = local - np.floor(local)

    u = u0 + local[:, 0] * (u1 - u0)
    v = v0 + local[:, 1] * (v1 - v0)
    return np.column_stack([u, v])


def solid_uv(region):
    u0, v0, u1, v1, *_ = region
    cu = 0.5 * (u0 + u1)
    cv = 0.5 * (v0 + v1)
    return np.array([[cu, cv], [cu, cv], [cu, cv]], dtype=np.float64)


def build_textured_mesh(scene: trimesh.Scene, parsed) -> tuple[trimesh.Trimesh, Image.Image]:
    parts = []
    all_tags = []
    for mesh in scene.geometry.values():
        m = mesh.copy()
        tags = remap_layer0_and_tag_pitch(m)
        tags = tag_textured_materials(m, parsed, tags)
        m2, tags2 = explode_mesh(m, tags)
        parts.append(m2)
        all_tags.append(tags2)

    combined = trimesh.util.concatenate(parts)
    tags = np.concatenate(all_tags)

    # Load needed textures
    needed = {t for t in tags if t}
    images = {}
    for tex_name in needed:
        # resolve via reverse lookup of TEXTURE_BY_MAT values
        path = None
        for folder in MATERIALS_DIR.iterdir() if MATERIALS_DIR.is_dir() else []:
            if not folder.is_dir():
                continue
            for f in folder.iterdir():
                if f.name.lower() == tex_name.lower():
                    path = f
                    break
            if path:
                break
        if path and path.is_file():
            images[tex_name] = Image.open(path)
        else:
            print(f"WARN: missing texture {tex_name}")

    # Solid colours for faces without textures
    fc = np.asarray(combined.visual.face_colors)
    solid_set = []
    solid_index = {}
    for i, c in enumerate(fc):
        if tags[i] is not None and tags[i] in images:
            continue
        key = color_key(c)
        if key not in solid_index:
            solid_index[key] = len(solid_set)
            solid_set.append(key)

    atlas, regions, _ = pack_atlas(images, solid_set)

    # Map solids
    for i, key in enumerate(solid_set):
        regions[f"color_{key}"] = regions[f"solid_{i}"]

    uvs = np.zeros((len(combined.vertices), 2), dtype=np.float64)
    normals = combined.face_normals
    faces = combined.faces
    verts = combined.vertices

    # Unique pitch fit: AABB of all pitch faces on XZ (Y-up mm mesh)
    pitch_bounds = None
    pitch_idxs = [i for i, t in enumerate(tags) if t == "pitch4.JPG"]
    if pitch_idxs:
        pitch_pts = verts[faces[pitch_idxs].reshape(-1)][:, [0, 2]]
        pitch_bounds = (pitch_pts.min(axis=0), pitch_pts.max(axis=0))

    for fi in range(len(faces)):
        tri = verts[faces[fi]]
        tag = tags[fi]
        if tag and tag in regions and tag in images:
            scale = TEX_SCALE_M.get(tag, 0.25)
            fit = pitch_bounds if tag == "pitch4.JPG" else None
            uvs[faces[fi]] = planar_uv_for_face(
                tri, normals[fi], scale, regions[tag], fit_bounds=fit
            )
        else:
            key = color_key(fc[fi])
            reg = regions[f"color_{key}"]
            uvs[faces[fi]] = solid_uv(reg)

    mat = PBRMaterial(baseColorTexture=atlas, baseColorFactor=[1, 1, 1, 1])
    combined.visual = TextureVisuals(uv=uvs, material=mat)
    return combined, atlas


def write_cs2_maps(atlas: Image.Image, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / "NA_LSVStadium_Base_BaseColorMap.png"
    atlas.convert("RGBA").save(base)
    # Flat OpenGL normal
    normal = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (128, 128, 255, 255))
    normal.save(out_dir / "NA_LSVStadium_Base_NormalMap.png")
    # MaskMap: R metallic=0, G coat=0, B=0, A glossiness≈80 (matte stadium)
    mask = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 80))
    mask.save(out_dir / "NA_LSVStadium_Base_MaskMap.png")
    print(f"Wrote CS2 maps → {out_dir}")
    return base


def main():
    import sys

    skp_path = Path(sys.argv[1]) if len(sys.argv) > 1 else SKP_DEFAULT
    if not skp_path.is_file():
        raise SystemExit(f"SKP not found: {skp_path}")
    if not MATERIALS_DIR.is_dir():
        print(f"WARN: materials dir missing ({MATERIALS_DIR}); solid colours only")

    print(f"Capturing scene from {skp_path} …")
    scene, parsed = capture_scene(skp_path)
    print(f"Geometry parts: {len(scene.geometry)}")

    mesh, atlas = build_textured_mesh(scene, parsed)
    print(f"Atlas {atlas.size}, mesh verts={len(mesh.vertices)} faces={len(mesh.faces)}")

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    glb_path = SOURCE_DIR / "LSV_stadium_textured.glb"
    mesh.export(str(glb_path), file_type="glb")
    print(f"Textured GLB → {glb_path} ({glb_path.stat().st_size} bytes)")

    # Also keep plain coloured GLB path used historically
    write_cs2_maps(atlas, OUT_DIR)
    atlas.save(TMP_DIR / "atlas_preview.png")
    print("Done")


if __name__ == "__main__":
    main()
