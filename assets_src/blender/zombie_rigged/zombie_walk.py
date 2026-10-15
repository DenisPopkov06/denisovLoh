import bpy, math, mathutils
from mathutils import Vector as V, Quaternion as Q, Matrix as M

scene = bpy.context.scene
arm = bpy.data.objects["Object_4"]
win = bpy.context.window_manager.windows[0]
screen = win.screen
area = next(a for a in screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
with bpy.context.temp_override(window=win, screen=screen, area=area, region=region):
    if screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)

src = bpy.data.actions["idlewalk"]
old = bpy.data.actions.get("zombie_stagger_walk")
if old:
    bpy.data.actions.remove(old)
act = src.copy(); act.name = "zombie_stagger_walk"; act.use_fake_user = True
src.use_fake_user = True
arm.animation_data.action = act
F0, F1 = int(src.frame_range[0]), int(src.frame_range[1])
L = F1 - F0
pb = arm.pose.bones

CHAIN_SWAY = ["hips_01", "spine_012", "chest_013", "neck_061", "head_062"]
ARM_CHAIN = {"L": [("L_arm_015", "L_elbow_016"), ("L_elbow_016", "L_wrist_017"), ("L_wrist_017", "L_middle1_026")],
             "R": [("R_arm_039", "R_elbow_040"), ("R_elbow_040", "R_wrist_041"), ("R_wrist_041", "R_middle1_050")]}
CHANGED = CHAIN_SWAY + [b for c in ARM_CHAIN.values() for b, _ in c]

# hide meshes so per-step depsgraph updates only evaluate the rig (much faster)
MESHES = ["Object_7", "ZombieVest", "ZombieShorts", "ZombieBelt", "Icosphere"]
hidden = [bpy.data.objects[n] for n in MESHES if n in bpy.data.objects]
for o in hidden:
    o.hide_viewport = True

# 1) remember the original local pose of the bones we rewrite, then drop their curves
orig = {}
for f in range(F0, F1 + 1):
    scene.frame_set(f)
    orig[f] = {n: pb[n].matrix_basis.copy() for n in CHANGED}
from bpy_extras import anim_utils
cbag = anim_utils.action_get_channelbag_for_slot(act, arm.animation_data.action_slot)
for fc in list(cbag.fcurves):
    for n in CHANGED:
        if fc.data_path.startswith('pose.bones["%s"]' % n):
            cbag.fcurves.remove(fc)
            break

aw = arm.matrix_world
arm_rot = aw.to_quaternion()
aw3_inv = aw.to_3x3().inverted()
def to_arm_dir(d):
    return (aw3_inv @ d).normalized()
def q_world(axis, deg):
    return Q((arm_rot.inverted() @ axis).normalized(), math.radians(deg))
def rot_about_head(p, q):
    m = p.matrix.copy()
    h = m.translation.copy()
    p.matrix = M.Translation(h) @ q.to_matrix().to_4x4() @ M.Translation(-h) @ m
def aim(p, child, target_arm_dir):
    cur = (pb[child].head - p.head).normalized()
    rot_about_head(p, cur.rotation_difference(target_arm_dir))
def wave(f, k, ph=0.0):
    return math.sin(2 * math.pi * (k * (f - F0) / L) + ph)
upd = bpy.context.view_layer.update
X, Y, Z = V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1))
FWD = V((0, -1, 0))

# arm targets (world): forward and roughly horizontal, left arm higher, limp hands
TARGET = {"L": [V((0.16, -1, 0.04)), V((0.04, -1, 0.10)), V((0.0, -1, -0.75))],
          "R": [V((-0.16, -1, -0.20)), V((-0.04, -1, -0.10)), V((0.0, -1, -0.85))]}

for f in range(F0, F1 + 1):
    scene.frame_set(f)
    for n in CHANGED:
        pb[n].matrix_basis = orig[f][n]
    upd()
    # staggering, hunched body: side-to-side roll, a bit of yaw, forward lean, lolling head
    sway = {
        "hips_01":   [(Y, 5.0 * wave(f, 4)), (Z, 4.0 * wave(f, 2, 0.7))],
        "spine_012": [(X, 8.0), (Y, 4.0 * wave(f, 4, 0.6))],
        "chest_013": [(X, 10.0), (Y, 3.0 * wave(f, 4, 1.1)), (Z, 3.0 * wave(f, 3, 0.3))],
        "neck_061":  [(X, 6.0), (Y, 4.0 * wave(f, 3, 1.4))],
        "head_062":  [(Y, -12.0 + 9.0 * wave(f, 3, 2.0)), (X, 6.0 * wave(f, 4, 0.9))],
    }
    for n in CHAIN_SWAY:
        q = Q()
        for axis, deg in sway[n]:
            q = q_world(axis, deg) @ q
        rot_about_head(pb[n], q)
        upd()
    for side, chain in ARM_CHAIN.items():
        ph = 0.0 if side == "L" else math.pi
        bob = q_world(X, 6.0 * wave(f, 4, ph)) @ q_world(Z, 4.0 * wave(f, 2, ph + 0.5))
        for (bone, child), t in zip(chain, TARGET[side]):
            aim(pb[bone], child, to_arm_dir(bob @ t.normalized()))
            upd()
    for n in CHANGED:
        p = pb[n]
        prop = "rotation_quaternion" if p.rotation_mode == 'QUATERNION' else "rotation_euler"
        p.keyframe_insert(prop, frame=f)
        p.keyframe_insert("location", frame=f)

for o in hidden:
    o.hide_viewport = False
scene.frame_set(F0)
with bpy.context.temp_override(window=win, screen=screen, area=area, region=region):
    bpy.ops.screen.animation_play()
print("baked", act.name, F0, F1, "fcurves", len(cbag.fcurves))
