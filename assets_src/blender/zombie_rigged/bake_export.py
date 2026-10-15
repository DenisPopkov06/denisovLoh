import bpy, os

OUT = r"C:\Users\Nikita\PycharmProjects\night-keeper\public\models\characters\zombie_walker_rigged.glb"
TARGET_HEIGHT = 1.8          # metres; the imported rig stands ~2.6 m tall
scene = bpy.context.scene
arm = bpy.data.objects["Object_4"]
win = bpy.context.window_manager.windows[0]
screen = win.screen
area = next(a for a in screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
def ctx(**kw):
    return bpy.context.temp_override(window=win, screen=screen, area=area, region=region, **kw)
with ctx():
    if screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

# rest pose for baking
ad = arm.animation_data
ad.action = None
for t in list(ad.nla_tracks):
    ad.nla_tracks.remove(t)
for p in arm.pose.bones:
    p.matrix_basis.identity()
bpy.context.view_layer.update()

scene.render.engine = 'CYCLES'
scene.cycles.samples = 8
scene.render.bake.margin = 8
scene.render.bake.use_clear = True

def select_only(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def bake_albedo(obj, size, image_name):
    img = bpy.data.images.get(image_name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(image_name, size, size, alpha=False)
    nodes = []
    for slot in obj.material_slots:
        nt = slot.material.node_tree
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = img; n.name = "BAKE_TARGET"
        nt.nodes.active = n
        nodes.append((nt, n))
    select_only(obj)
    with ctx(active_object=obj, selected_objects=[obj]):
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_clear=True)
    for nt, n in nodes:
        nt.nodes.remove(n)
    img.pack()
    return img

def export_material(name, image, roughness, metallic=0.0, normal_image=None, emission=None):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = image
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if normal_image:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nimg = nt.nodes.new("ShaderNodeTexImage"); nimg.image = normal_image
        normal_image.colorspace_settings.name = 'Non-Color'
        nt.links.new(nimg.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m

# ---------------------------------------------------------------- body
body = bpy.data.objects["Object_7"]
body_albedo = bake_albedo(body, 1024, "zombie_body_albedo")
normal_src = bpy.data.images["Image_2"]
normal_small = bpy.data.images.get("zombie_body_normal") or normal_src.copy()
normal_small.name = "zombie_body_normal"
if normal_small.size[0] > 1024:
    normal_small.scale(1024, 1024)
normal_small.pack()
body_mat = export_material("zombie_body", body_albedo, 0.85, normal_image=normal_small)
body.material_slots[0].material = body_mat      # eye slot keeps the emissive ZombieEye

# ---------------------------------------------------------------- clothes: fresh UVs, bake, simple materials
CLOTHES = {"ZombieVest": (1024, 0.92), "ZombieShorts": (1024, 0.9), "ZombieBelt": (512, 0.55)}
for name, (size, rough) in CLOTHES.items():
    obj = bpy.data.objects[name]
    me = obj.data
    uv = me.uv_layers.get("BakeUV") or me.uv_layers.new(name="BakeUV")
    me.uv_layers.active = uv
    uv.active_render = True
    select_only(obj)
    with ctx(active_object=obj, selected_objects=[obj], edit_object=obj):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
    img = bake_albedo(obj, size, name + "_albedo")
    # only the bake UVs go out to glTF
    for layer in [l for l in me.uv_layers if l.name != "BakeUV"]:
        me.uv_layers.remove(layer)
    new_mats = []
    for i, slot in enumerate(obj.material_slots):
        is_metal = slot.material and slot.material.name == "ZombieBuckle"
        new_mats.append(export_material(f"{name}_{i}", img, 0.38 if is_metal else rough, 0.35 if is_metal else 0.0))
    for slot, m in zip(obj.material_slots, new_mats):
        slot.material = m

# ---------------------------------------------------------------- scale to game size
root = bpy.data.objects["Sketchfab_model"]
bpy.context.view_layer.update()
zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
height = max(zs) - min(zs)
if abs(height - TARGET_HEIGHT) > 0.02:
    root.scale = root.scale * (TARGET_HEIGHT / height)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- one NLA track per game clip
for clip, action in (("walk", "zombie_walk_game"), ("attack", "zombie_attack"), ("death", "zombie_death")):
    tr = ad.nla_tracks.new(); tr.name = clip
    tr.strips.new(clip, 0, bpy.data.actions[action])
ad.action = None

# ---------------------------------------------------------------- export
def descendants(o):
    out = [o]
    for c in o.children:
        out += descendants(c)
    return out
export_objs = [o for o in descendants(root) if o.name != "Icosphere"]
for o in bpy.context.view_layer.objects:
    o.select_set(o in export_objs)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with ctx():
    bpy.ops.export_scene.gltf(
        filepath=OUT, export_format='GLB', use_selection=True,
        export_apply=True, export_animations=True, export_animation_mode='NLA_TRACKS',
        export_force_sampling=True, export_skins=True, export_yup=True,
        export_image_format='JPEG', export_jpeg_quality=85,
        export_draco_mesh_compression_enable=True,
    )
print("height was", round(height, 3), "-> exported", OUT, os.path.getsize(OUT) // 1024, "KB")
