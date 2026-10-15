import bpy, bmesh, mathutils, random, math

S = 0.0135
V = mathutils.Vector
body = bpy.data.objects["Object_7"]
arm_obj = bpy.data.objects["Object_4"]
def bhead(n): return arm_obj.matrix_world @ arm_obj.data.bones[n].head_local  # rest pose: clothes must not depend on the active animation frame

for n in ("ZombieVest", "ZombieShorts", "ZombieBelt"):
    o = bpy.data.objects.get(n)
    if o:
        d = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if d and d.users == 0:
            bpy.data.meshes.remove(d)

# ------------------------------------------------------------------ materials
def lin(c): return tuple((x / 255.0) ** 2.2 for x in c)

def cloth_mat(name, dark, light, rough=0.92, blotch=3.6, faded=None):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = 0.06
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = blotch; n1.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Generated"], n1.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (*lin(dark), 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (*lin(light), 1)
    nt.links.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 40.0; n2.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Generated"], n2.inputs["Vector"])
    r2 = nt.nodes.new("ShaderNodeValToRGB")
    r2.color_ramp.elements[0].color = (0.78, 0.78, 0.78, 1)
    r2.color_ramp.elements[1].color = (1.12, 1.12, 1.12, 1)
    nt.links.new(n2.outputs["Fac"], r2.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    nt.links.new(r2.outputs["Color"], mix.inputs[7])
    st = nt.nodes.new("ShaderNodeTexNoise")
    st.inputs["Scale"].default_value = 3.5; st.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Generated"], st.inputs["Vector"])
    sr = nt.nodes.new("ShaderNodeValToRGB")
    sr.color_ramp.elements[0].position = 0.56
    sr.color_ramp.elements[0].color = (0.42, 0.34, 0.30, 1)   # dark grime / dried blood
    sr.color_ramp.elements[1].position = 0.64
    sr.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(st.outputs["Fac"], sr.inputs["Fac"])
    mix2 = nt.nodes.new("ShaderNodeMix"); mix2.data_type = 'RGBA'; mix2.blend_type = 'MULTIPLY'
    mix2.inputs["Factor"].default_value = 1.0
    nt.links.new(mix.outputs[2], mix2.inputs[6])
    nt.links.new(sr.outputs["Color"], mix2.inputs[7])
    out_col = mix2.outputs[2]
    if faded:
        fn = nt.nodes.new("ShaderNodeTexNoise")
        fn.inputs["Scale"].default_value = 2.6; fn.inputs["Detail"].default_value = 3.0
        nt.links.new(tc.outputs["Generated"], fn.inputs["Vector"])
        fr = nt.nodes.new("ShaderNodeValToRGB")
        fr.color_ramp.elements[0].position = 0.55
        fr.color_ramp.elements[0].color = (0, 0, 0, 1)
        fr.color_ramp.elements[1].position = 0.72
        fr.color_ramp.elements[1].color = (0.75, 0.75, 0.75, 1)
        nt.links.new(fn.outputs["Fac"], fr.inputs["Fac"])
        mf = nt.nodes.new("ShaderNodeMix"); mf.data_type = 'RGBA'; mf.blend_type = 'MIX'
        nt.links.new(fr.outputs["Color"], mf.inputs["Factor"])
        nt.links.new(out_col, mf.inputs[6])
        mf.inputs[7].default_value = (*lin(faded), 1)
        out_col = mf.outputs[2]
    nt.links.new(out_col, bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m

shirt_mat = cloth_mat("ZombieCloth_Vest", (34, 31, 29), (98, 88, 76))
pants_mat = cloth_mat("ZombieCloth_Shorts", (40, 27, 27), (106, 76, 66), faded=(132, 104, 92))
patch_mat = cloth_mat("ZombieCloth_Patch", (70, 58, 48), (132, 110, 88), blotch=6.0)
belt_mat = cloth_mat("ZombieLeather_Belt", (14, 12, 12), (46, 40, 36), rough=0.55, blotch=5.0)
metal = bpy.data.materials.get("ZombieBuckle") or bpy.data.materials.new("ZombieBuckle")
metal.use_nodes = True
mb = next(n for n in metal.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
mb.inputs["Base Color"].default_value = (*lin((196, 186, 162)), 1)
mb.inputs["Metallic"].default_value = 0.35
mb.inputs["Roughness"].default_value = 0.38

# ------------------------------------------------------------------ helpers
def new_copy(name):
    mesh = body.data.copy(); mesh.name = name + "Mesh"
    obj = body.copy(); obj.name = name; obj.data = mesh
    bpy.context.scene.collection.objects.link(obj)
    for m in list(obj.modifiers):
        if m.type != 'ARMATURE':
            obj.modifiers.remove(m)
    bm = bmesh.new(); bm.from_mesh(mesh)
    return obj, bm

def cut(bm, mw, co_w, no_w):
    co = mw.inverted() @ co_w
    no = (mw.to_3x3().transposed() @ no_w).normalized()
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                           dist=1e-5, plane_co=co, plane_no=no)

def face_info(bm, mw, names):
    dl = bm.verts.layers.deform.active
    out = {}
    for f in bm.faces:
        acc = {}
        for v in f.verts:
            for gi, w in v[dl].items():
                acc[gi] = acc.get(gi, 0.0) + w
        g = names.get(max(acc, key=acc.get)) if acc else None
        c = mw @ f.calc_center_median()
        out[f] = (g, c)
    return out

def keep_faces(bm, keep):
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')

def push(bm, amount):
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * (amount / S)

def boundary_edges(bm, pred):
    return [e for e in bm.edges if e.is_boundary and pred(e)]

def extrude(bm, edges, move):
    res = bmesh.ops.extrude_edge_only(bm, edges=edges)
    nv = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
    for v in nv:
        move(v)
    return nv

def tatter(bm, mw, dir_fn, seed, cuts=2, long=(0.045, 0.09), p_long=0.3):
    rnd = random.Random(seed)
    edges = [e for e in bm.edges if e.is_boundary and
             dir_fn(mw @ e.verts[0].co) and dir_fn(mw @ e.verts[1].co)]
    if edges:
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts)
    m3 = mw.to_3x3().inverted()
    for v in bm.verts:
        if not any(e.is_boundary for e in v.link_edges):
            continue
        d = dir_fn(mw @ v.co)
        if not d:
            continue
        r = rnd.random()
        amt = rnd.uniform(*long) if r < p_long else (-rnd.uniform(0.008, 0.02) if r < p_long + 0.18 else rnd.uniform(0, 0.018))
        v.co += (m3 @ d).normalized() * (amt / S)

def finish(obj, bm, mats, thick):
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    obj.data.materials.clear()
    for m in mats:
        obj.data.materials.append(m)
    sol = obj.modifiers.new("Solidify", 'SOLIDIFY')
    sol.thickness = thick / S; sol.offset = -1.0
    obj.modifiers.move(obj.modifiers.find("Armature"), len(obj.modifiers) - 1)

names = {vg.index: vg.name for vg in body.vertex_groups}
TRUNK = {"hips_01", "spine_012", "chest_013", "L_shoulder_014", "R_shoulder_038", "L_leg_02", "R_leg_07"}
ARMS = {"L_arm_015": (bhead("L_arm_015"), bhead("L_elbow_016")),
        "R_arm_039": (bhead("R_arm_039"), bhead("R_elbow_040"))}
SLEEVE = 0.6
BELT_LO, BELT_HI = 1.395, 1.475
SHIRT_LO = 1.42
FRONT_Y = -0.17
# Opening profile (half width, z): narrow gap down the belly, widening into a
# deep V from mid-chest up to the neck - an unbuttoned shirt.
V_PROFILE = [(0.04, 1.40), (0.045, 1.72), (0.115, 2.12)]
V_TOP = V_PROFILE[-1][1]
LAPEL_FROM = 1.74
NECK = bhead("neck_061")

def v_half(z):
    pts = V_PROFILE
    if z <= pts[0][1]:
        return pts[0][0]
    for (w0, z0), (w1, z1) in zip(pts, pts[1:]):
        if z <= z1:
            return w0 + (w1 - w0) * (z - z0) / (z1 - z0)
    return pts[-1][0]

# ================================================================== SHIRT
obj, bm = new_copy("ZombieVest")
mw = obj.matrix_world.copy()
cut(bm, mw, V((0, 0, SHIRT_LO)), V((0, 0, 1)))
for sx in (-1, 1):
    for (w0, z0), (w1, z1) in zip(V_PROFILE, V_PROFILE[1:]):
        p1 = V((sx * w0, 0, z0)); p2 = V((sx * w1, 0, z1))
        d = (p2 - p1).normalized()
        cut(bm, mw, p1, V((d.z, 0, -d.x)))
for k, (a, b) in ARMS.items():
    ax = (b - a).normalized()
    cut(bm, mw, a + ax * SLEEVE * (b - a).length, ax)

info = face_info(bm, mw, names)
keep = set()
for f, (g, c) in info.items():
    if g in TRUNK and c.z >= SHIRT_LO:
        if c.y < FRONT_Y and c.z < V_TOP + 0.03 and abs(c.x) < v_half(c.z):
            continue  # open front
        keep.add(f)
    elif g in ARMS:
        a, b = ARMS[g]
        if (c - a).dot((b - a).normalized()) <= SLEEVE * (b - a).length:
            keep.add(f)
keep_faces(bm, keep)
# finer mesh so tears can have ragged outlines on this low-poly body
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)

# torn holes like the reference: two big ones low on the back, a rip high on the
# back, a couple on the front panels and one on the left sleeve
def side_of(c):
    return "back" if c.y > -0.12 else ("front" if c.y < -0.2 else None)
la, lb = ARMS["L_arm_015"]
sleeve_pt = la + (lb - la) * 0.3 + V((0, -0.035, 0.02))
HOLES = [("back", -0.07, 1.53, 0.05), ("back", 0.075, 1.50, 0.058), ("back", 0.01, 1.87, 0.035),
         ("front", 0.13, 1.60, 0.032), ("front", -0.15, 1.80, 0.026)]
rnd = random.Random(77)
hole_faces, hole_info = set(), []
for side, hx, hz, r in HOLES:
    lobes = [rnd.uniform(0.55, 1.4) for _ in range(7)]
    hole_info.append((side, hx, hz, r))
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        if side_of(c) != side:
            continue
        dx, dz = c.x - hx, c.z - hz
        k = (math.atan2(dz, dx) + math.pi) / (2 * math.pi) * 7
        i, t = int(k) % 7, k - int(k)
        rr = r * (lobes[i] * (1 - t) + lobes[(i + 1) % 7] * t)
        if dx * dx + dz * dz < rr * rr:
            hole_faces.add(f)
for f in bm.faces:
    if ((mw @ f.calc_center_median()) - sleeve_pt).length < 0.03:
        hole_faces.add(f)
bmesh.ops.delete(bm, geom=list(hole_faces), context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
# ragged hole outlines: jitter the rim in and out
m3i = mw.to_3x3().inverted()
for v in bm.verts:
    if not any(e.is_boundary for e in v.link_edges):
        continue
    w = mw @ v.co
    for side, hx, hz, r in hole_info:
        if side_of(w) == side and (w.x - hx) ** 2 + (w.z - hz) ** 2 < (1.6 * r) ** 2:
            d = V((w.x - hx, 0, w.z - hz)).normalized()
            j = d * rnd.uniform(-0.012, 0.022) + V((rnd.uniform(-0.01, 0.01), 0, rnd.uniform(-0.016, 0.006)))
            v.co += m3i @ j
            break
print("holes faces removed", len(hole_faces))
push(bm, 0.012)
# crumpled, untidy cloth: low-frequency lumps along the normal
from mathutils import noise as mnoise
bm.normal_update()
for v in bm.verts:
    w = mw @ v.co
    v.co += v.normal * ((mnoise.noise(w * 9.0) * 0.010 + mnoise.noise(w * 25.0) * 0.004) / S)

m3inv = mw.to_3x3().inverted()

def is_v_edge(w):
    # lies on the opening cut (front, |x| on the profile line)
    return w.y < FRONT_Y and SHIRT_LO + 0.03 < w.z < V_TOP + 0.04 and abs(abs(w.x) - v_half(w.z)) < 0.02

def neck_out(w):
    return V((w.x - NECK.x, w.y - NECK.y, 0)).normalized()

# lapels: wide soft flaps folded back over the chest, only on the upper V,
# tapering to nothing at mid-chest
for sx in (-1, 1):
    eds = boundary_edges(bm, lambda e: all(is_v_edge(mw @ v.co) and (mw @ v.co).x * sx > 0
                                           and (mw @ v.co).z > LAPEL_FROM for v in e.verts))
    def mv(v, sx=sx):
        w = mw @ v.co
        t = max(0.0, min(1.0, (w.z - LAPEL_FROM) / (V_TOP - LAPEL_FROM)))
        width = 0.06 * min(1.0, t / 0.55)  # grows from mid-chest, full width up to the collar
        v.co += m3inv @ V((sx * width, -0.007, 0.0))
    extrude(bm, eds, mv)
print("lapel/V edges", len(boundary_edges(bm, lambda e: all(is_v_edge(mw @ v.co) for v in e.verts))))

# Turn-down collar grown out of the shirt's own neckline, so it is one piece with
# the shirt. The neckline follows the bone-weight border and is a sawtooth on this
# low-poly mesh, so first snap it onto a smooth curve (teeth are raised, never
# lowered, so no skin shows), then extrude a short stand and the fold.
def ang(w):
    return math.atan2(w.x - NECK.x, -(w.y - NECK.y))   # 0 = front, +-pi = back
def neck_edge(e):
    a, b = (mw @ v.co for v in e.verts)
    if (b - a).length < 1e-6:
        return False
    return all(w.z > 1.95 and abs(w.x) < 0.2 and not is_v_edge(w) and abs(ang(w)) > 0.3 for w in (a, b))
neck = boundary_edges(bm, neck_edge)
ring = list({v for e in neck for v in e.verts})
def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi
samp = [(ang(mw @ v.co), math.hypot((mw @ v.co).x - NECK.x, (mw @ v.co).y - NECK.y), (mw @ v.co).z) for v in ring]
def win(a, w=0.3):
    return [s for s in samp if abs(wrap(s[0] - a)) < w] or [min(samp, key=lambda s: abs(wrap(s[0] - a)))]
zmax = {i: max(s[2] for s in win(samp[i][0])) for i in range(len(ring))}
inv = mw.inverted()
for i, v in enumerate(ring):
    a, r, z = samp[i]
    near = [j for j in range(len(ring)) if abs(wrap(samp[j][0] - a)) < 0.3]
    zs = sum(zmax[j] for j in near) / len(near)
    rs = max(r, sum(samp[j][1] for j in near) / len(near))
    d = V((math.sin(a), -math.cos(a), 0))
    v.co = inv @ (V((NECK.x, NECK.y, max(z, zs))) + d * rs)
# steps of the sawtooth collapse onto the curve; merge them so the ring is clean
bmesh.ops.remove_doubles(bm, verts=ring, dist=0.004 / S)
def flat_edge(e):
    a, b = (mw @ v.co for v in e.verts)
    return abs(b.z - a.z) < 0.6 * math.hypot(b.x - a.x, b.y - a.y)
# after snapping only the ends that dive down into the V are steep - leave those
# as plain shirt edge, otherwise the stand/fold turn them into thin fins
neck = [e for e in boundary_edges(bm, neck_edge) if flat_edge(e)]
print("neck ring verts", len({v for e in neck for v in e.verts}))

stand = bmesh.ops.extrude_edge_only(bm, edges=neck)
stand_v = [g for g in stand['geom'] if isinstance(g, bmesh.types.BMVert)]
for v in stand_v:
    w = mw @ v.co
    v.co += m3inv @ (V((0, 0, 0.025)) + neck_out(w) * 0.008)  # low stand
sv = set(stand_v)
top = [g for g in stand['geom'] if isinstance(g, bmesh.types.BMEdge) and all(x in sv for x in g.verts)]
fold = bmesh.ops.extrude_edge_only(bm, edges=top)
fold_v = [g for g in fold['geom'] if isinstance(g, bmesh.types.BMVert)]
for v in fold_v:
    w = mw @ v.co
    front = max(0.0, math.cos(ang(w)))                      # 1 at the front, 0 at the back
    d = (neck_out(w) * (1.0 - 0.25 * front) + V((0, -1, 0)) * 0.25 * front).normalized()
    v.co += m3inv @ (d * (0.046 + 0.01 * front) + V((0, 0, -(0.052 + 0.012 * front))))  # fold lies down near the neck
collar_faces = [f for f in bm.faces if any(v in sv or v in set(fold_v) for v in f.verts)]
print("collar faces", len(collar_faces))

def shirt_dir(w):
    if w.z < SHIRT_LO + 0.02:
        return None  # tucked under the belt
    for k, (a, b) in ARMS.items():
        ax = (b - a).normalized()
        if (w - a).dot(ax) > SLEEVE * (b - a).length * 0.75 and abs(w.x) > 0.3:
            return ax
    return None
tatter(bm, mw, shirt_dir, seed=31)
finish(obj, bm, [shirt_mat], 0.006)

# ================================================================== SHORTS
PANTS_LO, PANTS_HI = 0.88, BELT_HI
PANTS_G = {"hips_01", "spine_012", "L_leg_02", "R_leg_07", "L_knee_03", "R_knee_08"}
obj, bm = new_copy("ZombieShorts")
mw = obj.matrix_world.copy()
cut(bm, mw, V((0, 0, PANTS_LO)), V((0, 0, 1)))
cut(bm, mw, V((0, 0, PANTS_HI)), V((0, 0, 1)))
info = face_info(bm, mw, names)
keep_faces(bm, {f for f, (g, c) in info.items() if g in PANTS_G and PANTS_LO <= c.z <= PANTS_HI})
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)

# rips like the reference: holes on the thighs front and back, and a long split
# up the outer side of the left leg from the hem
def p_side(c):
    return "front" if c.y < -0.17 else ("back" if c.y > -0.08 else None)
P_HOLES = [("front", 0.16, 1.00, 0.042), ("front", 0.09, 0.93, 0.026),
           ("back", -0.15, 1.08, 0.048), ("back", 0.17, 0.95, 0.032)]
prnd = random.Random(91)
p_rm = set()
for side, hx, hz, r in P_HOLES:
    lobes = [prnd.uniform(0.55, 1.45) for _ in range(7)]
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        if p_side(c) != side:
            continue
        dx, dz = c.x - hx, c.z - hz
        k = (math.atan2(dz, dx) + math.pi) / (2 * math.pi) * 7
        i, t = int(k) % 7, k - int(k)
        rr = r * (lobes[i] * (1 - t) + lobes[(i + 1) % 7] * t)
        if dx * dx + dz * dz < rr * rr:
            p_rm.add(f)
for f in bm.faces:   # side split, widening toward the hem
    c = mw @ f.calc_center_median()
    if c.x < -0.18 and -0.24 < c.y < -0.06 and c.z < 0.99:
        half = 0.008 + 0.03 * max(0.0, (0.99 - c.z) / 0.11)
        if abs(c.y + 0.15) < half:
            p_rm.add(f)
bmesh.ops.delete(bm, geom=list(p_rm), context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
m3p = mw.to_3x3().inverted()
for v in bm.verts:   # ragged rims on the rips
    if any(e.is_boundary for e in v.link_edges) and (mw @ v.co).z > PANTS_LO + 0.015:
        v.co += m3p @ V((prnd.uniform(-0.012, 0.012), prnd.uniform(-0.006, 0.006), prnd.uniform(-0.014, 0.008)))
print("pants rip faces", len(p_rm))
push(bm, 0.016)
bm.normal_update()
for v in bm.verts:   # crumpled, baggy cloth
    w = mw @ v.co
    v.co += v.normal * ((mnoise.noise(w * 8.0) * 0.018 + mnoise.noise(w * 22.0) * 0.006) / S)

# baggy flared leg openings
for sx in (-1, 1):
    eds = boundary_edges(bm, lambda e: all((mw @ v.co).z < PANTS_LO + 0.02 and (mw @ v.co).x * sx > 0 for v in e.verts))
    ring = {v for e in eds for v in e.verts}
    cen = sum((v.co for v in ring), V()) / max(1, len(ring))
    def mv(v, cen=cen):
        rad = V((v.co.x - cen.x, v.co.y - cen.y, 0))
        v.co += rad * 0.22
        v.co.z -= 0.04 / S
    extrude(bm, eds, mv)
# Torn hem made of broad hanging strips (like the reference), not per-vertex
# needles: the drop varies smoothly around each leg, with a few long tongues
# of cloth and torn-out notches between them.
hrnd = random.Random(47)
hem_v = [v for v in bm.verts if any(e.is_boundary for e in v.link_edges) and (mw @ v.co).z < PANTS_LO]
for sx in (-1, 1):
    leg = [v for v in hem_v if (mw @ v.co).x * sx > 0]
    if not leg:
        continue
    cx = sum((mw @ v.co).x for v in leg) / len(leg)
    cy = sum((mw @ v.co).y for v in leg) / len(leg)
    tongues = []
    a = hrnd.uniform(0, 0.4)
    while a < 2 * math.pi:
        width = hrnd.uniform(0.14, 0.34)
        kind = hrnd.random()
        length = (hrnd.uniform(0.05, 0.14) if kind < 0.6 else
                  (-hrnd.uniform(0.035, 0.07) if kind < 0.78 else hrnd.uniform(0.0, 0.03)))
        tongues.append((a, width, length))
        a += width + hrnd.uniform(0.01, 0.08)
    for v in leg:
        w = mw @ v.co
        th = math.atan2(w.y - cy, w.x - cx) % (2 * math.pi)
        drop = 0.012 + 0.012 * mnoise.noise(V((math.cos(th) * 3, math.sin(th) * 3, sx * 7.0)))
        for a0, wd, ln in tongues:
            t = (th - a0) % (2 * math.pi)
            if t < wd:
                edge = min(t, wd - t) / (wd * 0.5)          # 0 at the strip sides, 1 mid
                drop += ln * min(1.0, edge * 3.5)
                break
        drop += hrnd.uniform(-0.008, 0.012)   # jagged, frayed tips
        v.co.z -= drop / S


# light worn patch on the right thigh (viewer's left)
bm.faces.ensure_lookup_table()
target = V((-0.17, -0.30, 1.03))
for f in bm.faces:
    if ((mw @ f.calc_center_median()) - target).length < 0.075:
        f.material_index = 1
finish(obj, bm, [pants_mat, patch_mat], 0.006)

# ================================================================== BELT
obj, bm = new_copy("ZombieBelt")
mw = obj.matrix_world.copy()
cut(bm, mw, V((0, 0, BELT_LO)), V((0, 0, 1)))
cut(bm, mw, V((0, 0, BELT_HI)), V((0, 0, 1)))
info = face_info(bm, mw, names)
keep_faces(bm, {f for f, (g, c) in info.items() if g in TRUNK | PANTS_G and BELT_LO <= c.z <= BELT_HI})
push(bm, 0.03)

# buckle: small box on the front, rigidly weighted to the hips bone
front_y = min((mw @ v.co).y for v in bm.verts if abs((mw @ v.co).x) < 0.05)
hips_idx = body.vertex_groups["hips_01"].index
dl = bm.verts.layers.deform.verify()
bc = V((0, front_y - 0.006, (BELT_LO + BELT_HI) / 2))
inv = mw.inverted()
# rectangular frame buckle with a prong (like the reference), not a solid block
W, H, T, D = 0.072, 0.058, 0.011, 0.008     # width, height, bar thickness, depth
bars = [((0, 0, H / 2 - T / 2), (W, D, T)), ((0, 0, -H / 2 + T / 2), (W, D, T)),
        ((-W / 2 + T / 2, 0, 0), (T, D, H)), ((W / 2 - T / 2, 0, 0), (T, D, H)),
        ((-0.004, -0.002, 0), (0.042, D * 0.7, 0.005))]                       # prong
buckle_faces = set()
for (cx, cy, cz), (sx, sy, sz) in bars:
    res = bmesh.ops.create_cube(bm, size=1.0)
    for v in res['verts']:
        v.co = inv @ (bc + V((cx + v.co.x * sx, cy + v.co.y * sy, cz + v.co.z * sz)))
        v[dl].clear(); v[dl][hips_idx] = 1.0
    buckle_faces |= {f for v in res['verts'] for f in v.link_faces}
for f in buckle_faces:
    f.material_index = 1
finish(obj, bm, [belt_mat, metal], 0.008)

print("built", {n: len(bpy.data.objects[n].data.vertices) for n in ("ZombieVest", "ZombieShorts", "ZombieBelt")})
