import bpy, math
from mathutils import Vector as V, Quaternion as Q, Matrix as M

scene = bpy.context.scene
arm = bpy.data.objects["Object_4"]
pb = arm.pose.bones
win = bpy.context.window_manager.windows[0]
screen = win.screen
area = next(a for a in screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
with bpy.context.temp_override(window=win, screen=screen, area=area, region=region):
    if screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)

walk = bpy.data.actions["zombie_stagger_walk"]
MESHES = ["Object_7", "ZombieVest", "ZombieShorts", "ZombieBelt", "Icosphere"]
hidden = [bpy.data.objects[n] for n in MESHES if n in bpy.data.objects]
for o in hidden:
    o.hide_viewport = True

aw = arm.matrix_world
aw_inv = aw.inverted()
X, Y, Z = V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1))
upd = bpy.context.view_layer.update

def wpos(n):
    return aw @ pb[n].head

def rot_about(p, q, pivot_arm):
    p.matrix = M.Translation(pivot_arm) @ q.to_matrix().to_4x4() @ M.Translation(-pivot_arm) @ p.matrix

def rot(n, axis, deg):          # rotate bone about its head, world axis (armature has no rotation)
    rot_about(pb[n], Q(axis, math.radians(deg)), pb[n].head.copy())
    upd()

def aim(n, child, d):           # point bone so that its child joint lies along world dir d
    p = pb[n]
    cur = (pb[child].head - p.head).normalized()
    rot_about(p, cur.rotation_difference(V(d).normalized()), p.head.copy())
    upd()

def root_rot(axis, deg, pivot_world):
    rot_about(pb["_rootJoint"], Q(axis, math.radians(deg)), aw_inv @ pivot_world)
    upd()

def root_move(dw):
    p = pb["_rootJoint"]
    p.matrix = M.Translation(aw_inv.to_3x3() @ V(dw)) @ p.matrix
    upd()

FEET = ["L_foot_05", "R_foot_010", "L_toes_06", "R_toes_011", "L_ankle_04", "R_ankle_09"]
def ground(bones, clearance):
    z = min(wpos(n).z for n in bones)
    root_move((0, 0, clearance - z))

ALL_BODY = ["head_062", "neck_061", "chest_013", "spine_012", "hips_01", "L_knee_03", "R_knee_08",
            "L_ankle_04", "R_ankle_09", "L_elbow_016", "R_elbow_040", "L_wrist_017", "R_wrist_041",
            "L_foot_05", "R_foot_010"]

def reset():
    for p in pb:
        p.matrix_basis = M.Identity(4)
    upd()

def stance(lean=0.0):
    """Hunched zombie stance with arms reaching forward (same look as the walk)."""
    rot("spine_012", X, 8 + lean * 0.5)
    rot("chest_013", X, 10 + lean * 0.5)
    rot("neck_061", X, 6)
    rot("head_062", Y, -10)
    for s, sx in (("L", 1), ("R", -1)):
        up, el, wr, fi = (("L_arm_015", "L_elbow_016", "L_wrist_017", "L_middle1_026") if s == "L"
                          else ("R_arm_039", "R_elbow_040", "R_wrist_041", "R_middle1_050"))
        hi = 0.04 if s == "L" else -0.2
        aim(up, el, (0.16 * sx, -1, hi))
        aim(el, wr, (0.04 * sx, -1, hi * 0.5 + 0.05))
        aim(wr, fi, (0, -1, -0.8))

def arms(spec):
    """spec: {"L": (upper, fore, hand), "R": (...)} world directions."""
    for s, (u, f, h) in spec.items():
        up, el, wr, fi = (("L_arm_015", "L_elbow_016", "L_wrist_017", "L_middle1_026") if s == "L"
                          else ("R_arm_039", "R_elbow_040", "R_wrist_041", "R_middle1_050"))
        aim(up, el, u); aim(el, wr, f); aim(wr, fi, h)

def legs(thigh_fwd, knee_bend, spread=0.0):
    for s, sx in (("L", 1), ("R", -1)):
        th, kn, an = (("L_leg_02", "L_knee_03", "L_ankle_04") if s == "L" else ("R_leg_07", "R_knee_08", "R_ankle_09"))
        a = math.radians(thigh_fwd)
        aim(th, kn, (spread * sx, -math.sin(a), -math.cos(a)))
        b = math.radians(thigh_fwd - knee_bend)
        aim(kn, an, (spread * sx * 0.5, -math.sin(b), -math.cos(b)))

def key_all(f):
    for p in pb:
        mode = "rotation_quaternion" if p.rotation_mode == 'QUATERNION' else "rotation_euler"
        p.keyframe_insert(mode, frame=f)
        p.keyframe_insert("location", frame=f)

def new_action(name):
    old = bpy.data.actions.get(name)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data.action = act
    return act

# ============================================================ ATTACK (loops, 24 fps)
def attack_pose(kind):
    reset()
    if kind == "ready":
        legs(12, 22)
        stance()
    elif kind == "windup":          # rear back, both arms raised over the head
        legs(14, 26)
        rot("spine_012", X, -4); rot("chest_013", X, -8); rot("neck_061", X, -6); rot("head_062", X, -12)
        arms({"L": ((0.35, 0.15, 1), (0.15, 0.6, 0.8), (0, 0.4, 1)),
              "R": ((-0.35, 0.15, 1), (-0.15, 0.6, 0.8), (0, 0.4, 1))})
    elif kind == "strike":          # lunge forward, claws slash down in front of the body
        legs(24, 44)
        rot("spine_012", X, 26); rot("chest_013", X, 26); rot("neck_061", X, 10); rot("head_062", X, 14)
        rot("jaw_065", X, 24)
        arms({"L": ((0.08, -1, -0.15), (-0.05, -1, -0.45), (0, -0.4, -1)),
              "R": ((-0.08, -1, -0.05), (0.05, -1, -0.35), (0, -0.4, -1))})
    elif kind == "follow":          # arms swept down and across, head still pushed forward
        legs(18, 32)
        rot("spine_012", X, 16); rot("chest_013", X, 18); rot("neck_061", X, 8); rot("head_062", X, 6)
        rot("jaw_065", X, 12)
        arms({"L": ((-0.2, -0.6, -0.8), (-0.4, -0.3, -0.85), (0, 0, -1)),
              "R": ((0.2, -0.6, -0.8), (0.4, -0.3, -0.85), (0, 0, -1))})
    ground(FEET, 0.0)

act = new_action("zombie_attack")
for f, kind in ((0, "ready"), (8, "windup"), (13, "strike"), (18, "follow"), (30, "ready")):
    attack_pose(kind)
    key_all(f)
attack_range = (0, 30)

# ============================================================ DEATH (plays once, ends lying down)
PIVOT = V((0, 0.08, 0.0))           # behind the heels: falls onto its back (+Y is behind)
def death_pose(kind):
    reset()
    if kind == "stand":
        legs(12, 22); stance(); ground(FEET, 0.0)
    elif kind == "hit":              # jerk back, arms fling up
        legs(10, 18)
        rot("spine_012", X, -10); rot("chest_013", X, -12); rot("neck_061", X, -15); rot("head_062", X, -20)
        rot("jaw_065", X, 25)
        arms({"L": ((0.7, 0.2, 0.7), (0.6, 0.0, 0.8), (0.3, 0, 1)),
              "R": ((-0.7, 0.2, 0.6), (-0.6, 0.1, 0.7), (-0.3, 0, 1))})
        ground(FEET, 0.0)
    elif kind == "buckle":           # knees give way, slumps
        legs(40, 85)
        rot("spine_012", X, 12); rot("chest_013", X, 10); rot("head_062", X, 20); rot("head_062", Y, 15)
        rot("jaw_065", X, 15)
        arms({"L": ((0.5, -0.1, -0.85), (0.2, 0.0, -1), (0, 0, -1)),
              "R": ((-0.5, 0.1, -0.85), (-0.2, 0, -1), (0, 0, -1))})
        ground(FEET, 0.0)
    elif kind in ("fall", "land", "bounce"):
        ang = {"fall": -55, "land": -88, "bounce": -82}[kind]
        if kind == "fall":
            legs(25, 45, spread=0.15)
        else:
            legs(6, 14, spread=0.12)   # legs lie (almost) flat on the ground
        rot("spine_012", X, -6); rot("head_062", Y, 25); rot("head_062", X, -10)
        rot("jaw_065", X, 18)
        arms({"L": ((0.9, 0.1, 0.4), (0.8, 0.3, 0.3), (0.6, 0.3, 0)),
              "R": ((-0.9, 0.2, 0.3), (-0.7, 0.4, 0.2), (-0.6, 0.3, 0))})
        root_rot(X, ang, PIVOT)
        if kind == "fall":
            ground(FEET, 0.0)
        else:
            ground(ALL_BODY, 0.07 if kind == "land" else 0.10)

act = new_action("zombie_death")
for f, kind in ((0, "stand"), (5, "hit"), (14, "buckle"), (24, "fall"), (32, "land"), (36, "bounce"),
                (41, "land"), (60, "land")):
    death_pose(kind)
    key_all(f)

for o in hidden:
    o.hide_viewport = False
arm.animation_data.action = walk
print("made zombie_attack", attack_range, "and zombie_death (0, 60)")
