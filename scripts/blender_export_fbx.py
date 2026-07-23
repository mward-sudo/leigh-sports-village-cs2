"""Convert textured LSV stadium GLB → CS2-ready FBX.

Pipeline assumptions:
  - Input GLB is already metres-or-mm from OpenSKP, with atlas UVs + BaseColor
  - Prefer source/LSV_stadium_textured.glb (from bake_sketchup_atlas.py)
  - Fall back to source/LSV_stadium.glb

Matches DanOkami CS2-Exporter-for-Blender prep:
  1. Author in meters (1 BU = 1 m) from OpenSKP mm GLB
  2. Clear glTF world parent
  3. Duplicate faces + flip (SketchUp is double-sided; CS2 culls backs)
  4. Rotate -90° X into mesh data (Z-up → Y-up rest pose)
  5. Scale ×100 into mesh data (m → cm numbers)
  6. Export FBX_SCALE_ALL, axis_up=Y, axis_forward=-Z

Without (4)+(5) CS2 shows a ~1 m edge-on speck instead of a ~120 m stadium.
Without (3) pitch + seat banks vanish (normals face inward/down in the SKP).
"""
import bpy
import math
import os
import shutil
from mathutils import Matrix

ROOT = "/Users/michael/Developer/cities skylines 2 mods/Leigh Sports Village Large Park Asset"
GLB_TEXTURED = os.path.join(ROOT, "source/LSV_stadium_textured.glb")
GLB_PLAIN = os.path.join(ROOT, "source/LSV_stadium.glb")
OUT_DIR = os.path.join(ROOT, "art_project/LeighSportsVillage/LSV_Stadium")
BLEND_PATH = os.path.join(ROOT, "source/LSV_stadium.blend")
FBX_PATH = os.path.join(OUT_DIR, "NA_LSVStadium_Base.fbx")

# Native CS2 Asset Importer suffixes (NOT Extra Assets Importer's *Map names)
BASECOLOR = os.path.join(OUT_DIR, "NA_LSVStadium_Base_BaseColor.png")
NORMALMAP = os.path.join(OUT_DIR, "NA_LSVStadium_Base_Normal.png")
MASKMAP = os.path.join(OUT_DIR, "NA_LSVStadium_Base_MaskMap.png")

# Legacy EAI-style names — keep copies so either importer finds maps
LEGACY = {
    BASECOLOR: os.path.join(OUT_DIR, "NA_LSVStadium_Base_BaseColorMap.png"),
    NORMALMAP: os.path.join(OUT_DIR, "NA_LSVStadium_Base_NormalMap.png"),
}

os.makedirs(OUT_DIR, exist_ok=True)

GLB_PATH = GLB_TEXTURED if os.path.isfile(GLB_TEXTURED) else GLB_PLAIN
print(f"Importing GLB: {GLB_PATH}")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0

bpy.ops.import_scene.gltf(filepath=GLB_PATH)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise RuntimeError("No meshes imported from GLB")

bpy.ops.object.select_all(action="DESELECT")
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()

obj = bpy.context.active_object

# glTF import parents meshes under a "world" empty — clear it or transforms fail
if obj.parent is not None:
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = mw

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

# OpenSKP / bake GLB is millimeters → meters
obj.scale = (0.001, 0.001, 0.001)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def vertex_aabb(mesh_obj):
    xs = [v.co.x for v in mesh_obj.data.vertices]
    ys = [v.co.y for v in mesh_obj.data.vertices]
    zs = [v.co.z for v in mesh_obj.data.vertices]
    return (
        (min(xs), max(xs)),
        (min(ys), max(ys)),
        (min(zs), max(zs)),
    )


def size_from_aabb(aabb):
    return tuple(round(hi - lo, 3) for lo, hi in aabb)


# Blender glTF import converts glTF Y-up → Blender Z-up. Ground = min_z.
aabb = vertex_aabb(obj)
min_x, max_x = aabb[0]
min_y, max_y = aabb[1]
min_z, max_z = aabb[2]
cx = (min_x + max_x) / 2.0
cy = (min_y + max_y) / 2.0
# Lift 5 cm so pitch doesn't z-fight with CS2 terrain
obj.data.transform(Matrix.Translation((-cx, -cy, -min_z + 0.05)))
obj.data.update()

# SketchUp faces are visually double-sided; OpenSKP exports one winding only.
# CS2/Unity backface-culls — without this the pitch + seat banks disappear.
faces_before = len(obj.data.polygons)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.duplicate()
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode="OBJECT")
print(f"Double-sided: {faces_before} → {len(obj.data.polygons)} faces")

meter_size = size_from_aabb(vertex_aabb(obj))
print(f"Authoring size (m): X={meter_size[0]}, Y={meter_size[1]}, Z={meter_size[2]}")
print(f"Verts={len(obj.data.vertices)}, Faces={len(obj.data.polygons)}")
print(f"UV layers={[uv.name for uv in obj.data.uv_layers]}")


def ensure_base_material(mesh_obj):
    while len(mesh_obj.data.materials) > 1:
        mesh_obj.data.materials.pop(index=len(mesh_obj.data.materials) - 1)

    mat = mesh_obj.data.materials[0] if mesh_obj.data.materials else None
    if mat is None:
        mat = bpy.data.materials.new(name="Base")
        mesh_obj.data.materials.append(mat)
    mat.name = "Base"
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex_path = BASECOLOR if os.path.isfile(BASECOLOR) else LEGACY[BASECOLOR]
    if os.path.isfile(tex_path):
        tex = nodes.new("ShaderNodeTexImage")
        tex.location = (-300, 0)
        img = bpy.data.images.load(tex_path, check_existing=True)
        tex.image = img
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        print(f"Bound BaseColor: {tex_path}")
    else:
        print("WARN: BaseColor missing; material has no texture")

    return mat


ensure_base_material(obj)

obj.name = "NA_LSVStadium_Base"
obj.data.name = "NA_LSVStadium_Base"
obj.location = (0.0, 0.0, 0.0)
obj.rotation_euler = (0.0, 0.0, 0.0)
obj.scale = (1.0, 1.0, 1.0)

# Editable metres-space .blend (before CS2 bake)
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

# --- CS2 bake (matches CS2-Exporter-for-Blender) ---
obj.data.transform(Matrix.Rotation(math.radians(-90.0), 4, "X"))
obj.data.update()
obj.data.transform(Matrix.Scale(100.0, 4))
obj.data.update()

# Re-centre: origin at ground centre (Y-up rest pose, ground at Y=0)
aabb = vertex_aabb(obj)
min_x, max_x = aabb[0]
min_y, max_y = aabb[1]
min_z, max_z = aabb[2]
cx = (min_x + max_x) / 2.0
cz = (min_z + max_z) / 2.0
obj.data.transform(Matrix.Translation((-cx, -min_y, -cz)))
obj.data.update()

baked = size_from_aabb(vertex_aabb(obj))
print(f"CS2-baked numbers (cm): X={baked[0]}, Y={baked[1]}, Z={baked[2]}")
print(
    f"Expected in-game size (m): X={baked[0]/100}, Y={baked[1]/100}, Z={baked[2]/100}"
)

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

# Do NOT embed textures — CS2 binds sidecar PNGs by naming convention
bpy.ops.export_scene.fbx(
    filepath=FBX_PATH,
    use_selection=True,
    global_scale=1.0,
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_ALL",
    axis_forward="-Z",
    axis_up="Y",
    object_types={"MESH"},
    use_mesh_modifiers=True,
    mesh_smooth_type="FACE",
    add_leaf_bones=False,
    bake_anim=False,
    path_mode="AUTO",
    embed_textures=False,
)

print(f"Exported FBX: {os.path.getsize(FBX_PATH)} bytes → {FBX_PATH}")

try:
    from PIL import Image
except ImportError:
    Image = None

if Image is not None:
    size = 2048
    if os.path.isfile(BASECOLOR):
        with Image.open(BASECOLOR) as im:
            size = im.size[0]
    elif os.path.isfile(LEGACY[BASECOLOR]):
        with Image.open(LEGACY[BASECOLOR]) as im:
            size = im.size[0]
    if not os.path.isfile(NORMALMAP):
        Image.new("RGBA", (size, size), (128, 128, 255, 255)).save(NORMALMAP)
        print(f"Wrote default Normal {NORMALMAP}")
    if not os.path.isfile(MASKMAP):
        Image.new("RGBA", (size, size), (0, 0, 0, 80)).save(MASKMAP)
        print(f"Wrote default MaskMap {MASKMAP}")

# Mirror legacy *Map filenames for Extra Assets Importer / older docs
for src, dst in LEGACY.items():
    if os.path.isfile(src):
        shutil.copy2(src, dst)
        print(f"Legacy copy → {dst}")

print("Done")
