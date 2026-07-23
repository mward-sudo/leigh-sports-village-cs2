"""Convert LSV stadium GLB → CS2-ready FBX.

Matches DanOkami CS2-Exporter-for-Blender prep:
  1. Author in meters (1 BU = 1 m) from OpenSKP mm GLB
  2. Clear glTF world parent
  3. Rotate -90° X into mesh data (Z-up → Y-up rest pose)
  4. Scale ×100 into mesh data (m → cm numbers)
  5. Export FBX_SCALE_ALL, axis_up=Y, axis_forward=-Z

Without (3)+(4) CS2 shows a ~1 m edge-on speck instead of a ~120 m stadium.
"""
import bpy
import math
import os
from mathutils import Matrix

ROOT = "/Users/michael/Developer/cities skylines 2 mods/Leigh Sports Village Large Park Asset"
GLB_PATH = os.path.join(ROOT, "source/LSV_stadium.glb")
OUT_DIR = os.path.join(ROOT, "art_project/LeighSportsVillage/LSV_Stadium")
BLEND_PATH = os.path.join(ROOT, "source/LSV_stadium.blend")
FBX_PATH = os.path.join(OUT_DIR, "NA_LSVStadium_Base.fbx")

os.makedirs(OUT_DIR, exist_ok=True)

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

# OpenSKP GLB is millimeters → meters
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


# Ground-centred origin (Z-up authoring space)
aabb = vertex_aabb(obj)
min_x, max_x = aabb[0]
min_y, max_y = aabb[1]
min_z, max_z = aabb[2]
cx = (min_x + max_x) / 2.0
cy = (min_y + max_y) / 2.0
# shift so ground (min_z) is at z=0 and XY centred
obj.data.transform(Matrix.Translation((-cx, -cy, -min_z)))
obj.data.update()

meter_size = size_from_aabb(vertex_aabb(obj))
print(f"Authoring size (m): X={meter_size[0]}, Y={meter_size[1]}, Z={meter_size[2]}")
print(f"Verts={len(obj.data.vertices)}, Faces={len(obj.data.polygons)}")

if not obj.data.materials:
    mat = bpy.data.materials.new(name="Base")
    obj.data.materials.append(mat)
elif obj.data.materials[0]:
    obj.data.materials[0].name = "Base"

obj.name = "NA_LSVStadium_Base"
obj.data.name = "NA_LSVStadium_Base"
obj.location = (0.0, 0.0, 0.0)
obj.rotation_euler = (0.0, 0.0, 0.0)
obj.scale = (1.0, 1.0, 1.0)

# Editable meters-space .blend (Z-up, before CS2 bake)
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

# --- CS2 bake (matches CS2-Exporter-for-Blender) ---
# -90° X: height Z → Y
obj.data.transform(Matrix.Rotation(math.radians(-90.0), 4, "X"))
obj.data.update()
# ×100: meters → centimetre numbers for Unity/CS2 File Scale
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
    path_mode="COPY",
    embed_textures=True,
)

print(f"Exported FBX: {os.path.getsize(FBX_PATH)} bytes → {FBX_PATH}")
print("Done")
