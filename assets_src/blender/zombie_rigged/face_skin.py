import bpy, math, bmesh
from mathutils import Vector as V, Quaternion as Q, Matrix as M

def lin(c): return tuple((x / 255.0) ** 2.2 for x in c)

body = bpy.data.objects["Object_7"]
arm = bpy.data.objects["Object_4"]
me = body.data
mw = body.matrix_world
names = {vg.index: vg.name for vg in body.vertex_groups}
def dom(v):
    return names[max(v.groups, key=lambda g: g.weight).group] if v.groups else None

# ---------------------------------------------------------------- skin: bone-tan, matte
mat = bpy.data.materials["zombie1"]
nt = mat.node_tree
for n in [n for n in nt.nodes if n.name.startswith("ZS_")]:
    nt.nodes.remove(n)
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
albedo = next(n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image and n.image.name == "Image_0")
for l in list(bsdf.inputs["Base Color"].links):
    nt.links.remove(l)
hsv = nt.nodes.new("ShaderNodeHueSaturation"); hsv.name = "ZS_hsv"
hsv.inputs["Saturation"].default_value = 0.55
hsv.inputs["Value"].default_value = 1.35
nt.links.new(albedo.outputs["Color"], hsv.inputs["Color"])
tint = nt.nodes.new("ShaderNodeMix"); tint.name = "ZS_tint"
tint.data_type = 'RGBA'; tint.blend_type = 'MULTIPLY'
tint.inputs["Factor"].default_value = 0.75
nt.links.new(hsv.outputs["Color"], tint.inputs[6])
tint.inputs[7].default_value = (*lin((246, 206, 156)), 1)          # warm bone / sand
attr = nt.nodes.new("ShaderNodeAttribute"); attr.name = "ZS_shade"
attr.attribute_name = "zombie_shade"
shade = nt.nodes.new("ShaderNodeMix"); shade.name = "ZS_shademix"
shade.data_type = 'RGBA'; shade.blend_type = 'MULTIPLY'
shade.inputs["Factor"].default_value = 1.0
nt.links.new(tint.outputs[2], shade.inputs[6])
nt.links.new(attr.outputs["Color"], shade.inputs[7])
nt.links.new(shade.outputs[2], bsdf.inputs["Base Color"])
# matte: remap the roughness map into a dry, high range
rough_src = bsdf.inputs["Roughness"].links[0].from_socket if bsdf.inputs["Roughness"].is_linked else None
mr = nt.nodes.new("ShaderNodeMapRange"); mr.name = "ZS_rough"
mr.inputs["To Min"].default_value = 0.68; mr.inputs["To Max"].default_value = 0.95
if rough_src:
    for l in list(bsdf.inputs["Roughness"].links):
        nt.links.remove(l)
    nt.links.new(rough_src, mr.inputs["Value"])
else:
    mr.inputs["Value"].default_value = 0.5
nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
bsdf.inputs["Specular IOR Level"].default_value = 0.25

# ---------------------------------------------------------------- dark eye sockets (per-vertex shade)
def bone_w(n): return arm.matrix_world @ arm.data.bones[n].head_local
eyes = [bone_w("L_eye_063"), bone_w("R_eye_064")]
attr_data = me.color_attributes.get("zombie_shade") or me.color_attributes.new("zombie_shade", 'FLOAT_COLOR', 'POINT')
for v in me.vertices:
    w = mw @ v.co
    d = min((w - e).length for e in eyes)
    k = 1.0
    if dom(v) not in ("L_eye_063", "R_eye_064"):
        k = 0.16 + 0.84 * max(0.0, min(1.0, (d - 0.03) / 0.05))
    attr_data.data[v.index].color = (k, k, k, 1.0)

# ---------------------------------------------------------------- glowing pale eyes
eye_mat = bpy.data.materials.get("ZombieEye") or bpy.data.materials.new("ZombieEye")
eye_mat.use_nodes = True
eb = next(n for n in eye_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
eb.inputs["Base Color"].default_value = (*lin((222, 220, 196)), 1)
eb.inputs["Emission Color"].default_value = (*lin((232, 236, 205)), 1)
eb.inputs["Emission Strength"].default_value = 4.0  # must read in the dark night scene
eb.inputs["Roughness"].default_value = 0.25
if "ZombieEye" not in [m.name for m in me.materials if m]:
    me.materials.append(eye_mat)
eye_idx = [i for i, m in enumerate(me.materials) if m and m.name == "ZombieEye"][0]
eye_verts = {v.index for v in me.vertices if dom(v) in ("L_eye_063", "R_eye_064")}
n_eye = 0
for p in me.polygons:
    if all(i in eye_verts for i in p.vertices):
        p.material_index = eye_idx
        n_eye += 1
me.update()

# ---------------------------------------------------------------- open jaw in the walk (slow chewing)
pj = arm.pose.bones["jaw_065"]
saved_action = arm.animation_data.action
arm.animation_data.action = None
for p in arm.pose.bones:
    p.matrix_basis = M.Identity(4)
bpy.context.view_layer.update()
def jaw_q(deg):
    pj.matrix_basis = M.Identity(4)
    bpy.context.view_layer.update()
    h = pj.head.copy()
    pj.matrix = M.Translation(h) @ Q((1, 0, 0), math.radians(deg)).to_matrix().to_4x4() @ M.Translation(-h) @ pj.matrix
    bpy.context.view_layer.update()
    return pj.matrix_basis.to_quaternion()
q_lo, q_hi = jaw_q(14), jaw_q(26)
pj.matrix_basis = M.Identity(4)
walk = bpy.data.actions["zombie_stagger_walk"]
arm.animation_data.action = walk
from bpy_extras import anim_utils
cbag = anim_utils.action_get_channelbag_for_slot(walk, arm.animation_data.action_slot)
for fc in list(cbag.fcurves):
    if fc.data_path.startswith('pose.bones["jaw_065"]'):
        cbag.fcurves.remove(fc)
pj.rotation_mode = 'QUATERNION'
F0, F1 = int(walk.frame_range[0]), int(walk.frame_range[1])
steps = 8
for i in range(steps + 1):
    f = F0 + (F1 - F0) * i / steps
    pj.rotation_quaternion = q_lo if i % 2 == 0 else q_hi
    pj.keyframe_insert("rotation_quaternion", frame=f)
arm.animation_data.action = saved_action
print("eye faces", n_eye, "eye verts", len(eye_verts))
