# Leigh Sports Village — Large Park Asset (CS2)

Custom **Leigh Sports Village stadium** for *Cities: Skylines II* **1.6**, converted from SketchUp (`LSV stadium.skp`).

Import and publish with the **native in-game Asset Importer** (Editor). No Extra Assets Importer / community JSON packs required.

Official overview: [Development Diary: Adding Custom Assets](https://colossalorder.fi/news/development-diary-custom-assets/) · Technical specs: [Asset Creation Guide (wiki)](https://cs2.paradoxwikis.com/Asset_Creation_Guide)

## Game-ready files

| Path | Role |
|------|------|
| `art_project/` | **Project Root** for the Asset Importer |
| `art_project/LeighSportsVillage/LSV_Stadium/` | **Assets Folder** for this stadium (folder underscores OK) |
| `…/NA_LSVStadium_Base.fbx` | Main mesh (CS2-baked −90°X + ×100; origin at ground centre) |
| `…/NA_LSVStadium_Base_BaseColorMap.png` | 2048×2048 atlas (SketchUp colours + key textures) |
| `…/NA_LSVStadium_Base_NormalMap.png` | Flat OpenGL normal (optional but included) |
| `…/NA_LSVStadium_Base_MaskMap.png` | Default MaskMap (low metal / moderate gloss) |
| `…/icon.png` | UI thumbnail |

**Naming rule:** Asset names must be a single token with **no underscores**. Pattern: `{Theme}_{AssetName}_{Module}` / `{Theme}_{AssetName}_{Module}_BaseColorMap.png` (e.g. `NA` + `LSVStadium` + `Base`).

### Model stats (CS2-ready export)

- **Source:** SketchUp 3D Warehouse [Leigh Sports Village Stadium](https://3dwarehouse.sketchup.com/model/a7d7c98e6df34ce6a7174eba4ed97c53/Leigh-Sports-Village-Stadium) (`LSV stadium.skp`)
- **Footprint:** ~119 m × 151 m  
- **Height:** ~13 m  
- **Geometry:** ~49.9k vertices (exploded for atlas UVs), 16,647 faces  
- **Export bake:** −90° X + ×100 (same as [CS2 Exporter for Blender](https://github.com/DanOkami/CS2-Exporter-for-Blender)) so Unity/CS2 File Scale lands at 1 m = 1 m  
- **Textures:** Single `Base` material with a 2048 atlas baked from SketchUp face colours + embedded textures (pitch, seats, cladding, metal, etc.). Original SKP had 42 materials — native CS2 importer uses one atlas.

---

## Import into CS2 1.6 (native Asset Importer)

You need a **Windows** install of Cities: Skylines II **1.6+** with the Editor (Steam / Xbox / Epic). GeForce NOW on Mac cannot run the Editor; copy this repo to a Windows PC (or AirGPU Windows session) first.

### 1. Put the files on the Windows machine

Copy the whole `art_project` folder somewhere easy to browse, for example:

```text
C:\CS2_Assets\art_project\
```

Keep this structure intact:

```text
art_project/
└── LeighSportsVillage/
    └── LSV_Stadium/
        ├── NA_LSVStadium_Base.fbx
        ├── NA_LSVStadium_Base_BaseColorMap.png
        ├── NA_LSVStadium_Base_NormalMap.png
        ├── NA_LSVStadium_Base_MaskMap.png
        └── icon.png
```

### 2. Open the Editor

1. Launch **Cities: Skylines II** (fully updated to **1.6**).
2. From the **Main Menu**, open the **Editor** (same Editor as maps — there is no separate asset Editor).
3. Optional: load a map with roads for scale reference, or use the default green terrain.

### 3. Import with Asset Importer

1. Click **Asset Importer** (toolbar; panel opens on the right).
2. Set:
   - **Project Root** → the `art_project` folder  
     Example: `C:\CS2_Assets\art_project`
   - **Assets Folder** → `LeighSportsVillage\LSV_Stadium`  
     Example: `C:\CS2_Assets\art_project\LeighSportsVillage\LSV_Stadium`
3. Confirm the importer lists at least:
   - `NA_LSVStadium_Base.fbx`
   - `NA_LSVStadium_Base_BaseColorMap.png`
   - `icon.png`
4. Choose a **Prefab Preset**:
   - **Static Object** — large decorative prop (best first test)
   - **Building** — lot-based park / signature building (configure lot after import)
   - **Existing Prefab in Project** — copy components from a similar in-game stadium/park building
5. Click **Import** and wait until processing finishes.
6. **Place** the new asset in the scene so you can edit it.

### 4. Configure the asset

Select the placed asset. Use the **Object Info Panel** (right) to set:

- Display name: `Leigh Sports Village Stadium`
- Cost, category (e.g. Parks / Recreation), consumptions, capacity as needed
- If **Building**: lot width ≈ **120**, depth ≈ **150** (max lot is 1000×1000 in 1.5.2+ / 1.6)
- Paths / pathfinding areas / pedestrian access if citizens should enter the grounds
- Props and surfaces via **Asset Browser** (enable *Binds overlapping items to a building* when decorating)

### 5. Save locally

In the **Workspace** panel (left):

1. Find your asset in the list.
2. Click **Save** to write a local prefab.

Saved files typically land here on Windows:

```text
%USERPROFILE%\AppData\LocalLow\Colossal Order\Cities Skylines II\StreamingAssets~
```

(You may also see related data under `StreamingData~` depending on session.)

### 6. Package and publish to Paradox Mods

Still in **Workspace** (1.6 / Asset Mods Editor flow):

1. **Package** — packs selected items into a `.cok` (virtual texturing / packaging).
2. **Share** — open the share UI, add description + screenshots.
3. **Submit** — upload to **Paradox Mods** (PDX account required).

You can re-open packaged assets from Workspace in later Editor sessions.

---

## Prerequisites (this Mac — conversion only)

| Tool | Use |
|------|-----|
| Blender 5.2 | `/Applications/Blender.app` — FBX export |
| Python 3 + `openskp` / `scipy` / `pillow` / `trimesh` | SketchUp parse + atlas bake |

CS2 itself is not required on the Mac. Final import/publish is **in-game on Windows**.

---

## Manual polish (optional)

1. **Materials** — Atlas already covers SketchUp colours/textures on one `Base` slot. For glass/emissive CS2 slots (`Gls`, `Win`, …) split meshes in Blender via [CS2 Exporter for Blender](https://github.com/DanOkami/CS2-Exporter-for-Blender).
2. **Asset type** — prop vs park building vs signature stadium; tune lot, park area, entertainment in the Editor.
3. **LODs** — optional `_LOD1` / `_LOD2` FBX meshes for city-scale performance.

**Visual limits vs SketchUp / 3D Warehouse:** OpenSKP does not export original SketchUp UVs. Pitch markings are planar-fitted; other textured faces use planar/box-style projection. Unpainted Layer0 faces (SketchUp UI red) are remapped to pitch green or neutral grey. Expect a close colour/read of the warehouse model, not a pixel-perfect material match.

---

## Re-convert from the original SKP

```bash
"./scripts/convert_skp_to_fbx.sh"
# or pass a path:
"./scripts/convert_skp_to_fbx.sh" "/path/to/LSV stadium.skp"
```

Requires: `pip install openskp scipy pillow trimesh numpy`, Blender at `/Applications/Blender.app`.

Default SKP path in the script: `~/Downloads/LSV stadium.skp`.

### Source / intermediates in this repo

| Path | Description |
|------|-------------|
| `source/LSV_stadium.glb` | Intermediate GLB from SketchUp (face colours) |
| `source/LSV_stadium_textured.glb` | Atlas-UV textured GLB for Blender |
| `source/LSV_stadium.blend` | Blender scene (metres, before CS2 bake) |
| `source/LSV_stadium_metadata.json` | Parsed SKP metadata |
| `scripts/convert_skp_to_fbx.sh` | Conversion driver (SKP → atlas → FBX) |
| `scripts/bake_sketchup_atlas.py` | Face-colour + texture atlas bake |
| `scripts/blender_export_fbx.py` | Blender mm→m + CS2 −90°/×100 FBX bake |

Original SketchUp file is **not** in the repo (user Downloads). Parsed with [OpenSKP](https://github.com/iamahsanmehmood/openskp).

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Model tiny / edge-on speck | Re-copy the latest `NA_LSVStadium_Base.fbx`. Export must bake **×100** and **−90° X** (CS2/Unity FBX). Plain mm→m without that bake imports at ~1 m and tipped. |
| Pink / missing textures | Keep `NA_LSVStadium_Base_BaseColorMap.png` in the Assets Folder; square PNG 512–4096 px. |
| Import list empty | Project Root must be `art_project`, **not** only `LSV_Stadium`. |
| `FormatException` / ParseName fails | AssetName must not contain `_`. Use `LSVStadium`, not `LSV_Stadium`, in mesh/texture filenames. |
| Asset missing from build menu | Save in Workspace; set UI category / unlock as needed. |
| Cannot open Editor (Mac / GFN) | Use a Windows PC or cloud Windows (e.g. AirGPU); GFN Mac does not provide the Editor. |

---

## License

Model source is user-provided. Check SketchUp / texture licenses before publishing to Paradox Mods.
