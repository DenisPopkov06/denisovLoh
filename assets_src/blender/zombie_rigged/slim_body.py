import bpy, mathutils

V = mathutils.Vector
body = bpy.data.objects["Object_7"]
arm_obj = bpy.data.objects["Object_4"]
bones = arm_obj.data.bones
def h(n): return arm_obj.matrix_world @ bones[n].head_local

# Keep the untouched mesh once so the slimming can always be redone/reverted.
orig = bpy.data.meshes.get("mesh_zombie1_0_orig")
if orig is None:
    orig = body.data.copy(); orig.name = "mesh_zombie1_0_orig"; orig.use_fake_user = True

# bone -> (segment start, segment end, keep factor). Factor < 1 pulls flesh toward the bone.
SEG = {
    "hips_01":        (h("hips_01"), h("spine_012"), 0.84),
    "spine_012":      (h("spine_012"), h("chest_013"), 0.78),
    "chest_013":      (h("chest_013"), h("neck_061"), 0.80),
    "L_shoulder_014": (h("L_shoulder_014"), h("L_arm_015"), 0.82),
    "R_shoulder_038": (h("R_shoulder_038"), h("R_arm_039"), 0.82),
    "L_arm_015":      (h("L_arm_015"), h("L_elbow_016"), 0.78),
    "R_arm_039":      (h("R_arm_039"), h("R_elbow_040"), 0.78),
    "L_elbow_016":    (h("L_elbow_016"), h("L_wrist_017"), 0.82),
    "R_elbow_040":    (h("R_elbow_040"), h("R_wrist_041"), 0.82),
    "L_leg_02":       (h("L_leg_02"), h("L_knee_03"), 0.80),
    "R_leg_07":       (h("R_leg_07"), h("R_knee_08"), 0.80),
    "L_knee_03":      (h("L_knee_03"), h("L_ankle_04"), 0.84),
    "R_knee_08":      (h("R_knee_08"), h("R_ankle_09"), 0.84),
    "neck_061":       (h("neck_061"), h("head_062"), 0.90),
}

def closest_on_seg(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return a + ab * t

mw = body.matrix_world
inv = mw.inverted()
names = {vg.index: vg.name for vg in body.vertex_groups}
src = orig.vertices
dst = body.data.vertices
moved = 0
for v_src, v_dst in zip(src, dst):
    p = mw @ v_src.co
    tot = 0.0; target = V(); fac = 0.0
    for g in v_src.groups:
        n = names[g.group]
        tot += g.weight
        if n in SEG:
            a, b, k = SEG[n]
            target += closest_on_seg(p, a, b) * g.weight
            fac += k * g.weight
        else:
            target += p * g.weight
            fac += 1.0 * g.weight
    if tot <= 0:
        v_dst.co = v_src.co
        continue
    target /= tot; fac /= tot
    if fac < 0.999:
        moved += 1
    v_dst.co = inv @ (target + (p - target) * fac)
body.data.update()
print("slimmed verts", moved)
