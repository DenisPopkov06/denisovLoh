import bpy, math
from mathutils import Vector as V, Quaternion as Q, Matrix as M

# In-place game walk: frames 138..168 of the designer's idlewalk are a clean
# treadmill step cycle (hips don't travel) - the game moves the zombie itself.
SRC_A, SRC_B = 138, 168
L = SRC_B - SRC_A                      # 30 frames, two steps
scene = bpy.context.scene
arm = bpy.data.objects["Object_4"]
pb = arm.pose.bones
ad = arm.animation_data
src = bpy.data.actions["idlewalk"]

MESHES = ["Object_7", "ZombieVest", "ZombieShorts", "ZombieBelt", "Icosphere"]
hidden = [bpy.data.objects[n] for n in MESHES if n in bpy.data.objects]
for o in hidden:
    o.hide_viewport = True

# 1) sample the source pose of every bone
ad.action = src
orig = {}
for g in range(L + 1):
    scene.frame_set(SRC_A + g)
    orig[g] = {p.name: p.matrix_basis.copy() for p in pb}

old = bpy.data.actions.get("zombie_walk_game")
if old:
    bpy.data.actions.remove(old)
act = bpy.data.actions.new("zombie_walk_game"); act.use_fake_user = True
ad.action = act

upd = bpy.context.view_layer.update
X, Y, Z = V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1))
def q_world(axis, deg): return Q(axis, math.radians(deg))      # armature has no rotation
def rot_about_head(p, q):
    m = p.matrix.copy(); h = m.translation.copy()
    p.matrix = M.Translation(h) @ q.to_matrix().to_4x4() @ M.Translation(-h) @ m
def aim(p, child, d):
    cur = (pb[child].head - p.head).normalized()
    rot_about_head(p, cur.rotation_difference(V(d).normalized()))
def wave(g, k, ph=0.0): return math.sin(2 * math.pi * k * g / L + ph)

ARM_CHAIN = {"L": [("L_arm_015", "L_elbow_016"), ("L_elbow_016", "L_wrist_017"), ("L_wrist_017", "L_middle1_026")],
             "R": [("R_arm_039", "R_elbow_040"), ("R_elbow_040", "R_wrist_041"), ("R_wrist_041", "R_middle1_050")]}
TARGET = {"L": [V((0.16, -1, 0.04)), V((0.04, -1, 0.10)), V((0.0, -1, -0.75))],
          "R": [V((-0.16, -1, -0.20)), V((-0.04, -1, -0.10)), V((0.0, -1, -0.85))]}
SWAY = ["hips_01", "spine_012", "chest_013", "neck_061", "head_062"]

pj = pb["jaw_065"]
def jaw_open(deg):
    rot_about_head(pj, q_world(X, deg))

for g in range(L + 1):
    for p in pb:
        p.matrix_basis = orig[g][p.name]
    upd()
    # sway tied to the steps: roll once per step (k=2), slower yaw/head loll (k=1)
    sway = {
        "hips_01":   [(Y, 5.0 * wave(g, 2)), (Z, 4.0 * wave(g, 1, 0.7))],
        "spine_012": [(X, 8.0), (Y, 4.0 * wave(g, 2, 0.6))],
        "chest_013": [(X, 10.0), (Y, 3.0 * wave(g, 2, 1.1)), (Z, 3.0 * wave(g, 1, 0.3))],
        "neck_061":  [(X, 6.0), (Y, 4.0 * wave(g, 1, 1.4))],
        "head_062":  [(Y, -12.0 + 9.0 * wave(g, 1, 2.0)), (X, 6.0 * wave(g, 2, 0.9))],
    }
    for n in SWAY:
        q = Q()
        for axis, deg in sway[n]:
            q = q_world(axis, deg) @ q
        rot_about_head(pb[n], q)
        upd()
    for side, chain in ARM_CHAIN.items():
        ph = 0.0 if side == "L" else math.pi
        bob = q_world(X, 6.0 * wave(g, 2, ph)) @ q_world(Z, 4.0 * wave(g, 1, ph + 0.5))
        for (bone, child), t in zip(chain, TARGET[side]):
            aim(pb[bone], child, bob @ t.normalized())
            upd()
    jaw_open(20 + 6 * wave(g, 1))
    upd()
    for p in pb:
        mode = "rotation_quaternion" if p.rotation_mode == 'QUATERNION' else "rotation_euler"
        p.keyframe_insert(mode, frame=g)
        p.keyframe_insert("location", frame=g)

for o in hidden:
    o.hide_viewport = False
print("zombie_walk_game baked", act.frame_range[:])
