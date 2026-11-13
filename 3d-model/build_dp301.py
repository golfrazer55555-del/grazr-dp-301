"""GRAZR DP-301 putter - procedural Blender model.

Run:  python3 3d-model/build_dp301.py            (needs `pip install bpy`)
  or: blender -b -P 3d-model/build_dp301.py

Geometry is authored in millimetres and parented to a root empty scaled
0.001, so the scene / glTF are in metres while STL exports stay in mm.

Coordinate frame (model space, mm):
  X = heel(-) -> toe(+), Y = face(0) -> back(+), Z = sole(0) -> up
Specs: loft 3 deg, lie 74 deg, face length 108 mm, shaft bore 9.4 mm (.370"),
SUS304 (7.93 g/cm^3), diamond face milling, black coated CNC finish.
"""
import math
import os
import sys

import bpy  # noqa: E402  (must come before bmesh)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE
RENDER = "--no-render" not in sys.argv

# ---------------------------------------------------------------- specs (mm)
FACE_LEN = 108.0
HEAD_H = 25.0            # head height == wing diameter
R_WING = HEAD_H / 2
X_WING = FACE_LEN / 2 - R_WING      # wing axis x
BAR_T = 13.0             # face bar thickness (front->back)
WING_LEN = 67.0          # wing length from face
WEB_H = 6.0              # height of the centre web
TARGET_G = 395.0         # head weight spec
PLUG_LEN = 5.0           # threaded plug of the end weights
CUT_R = 23.5             # ball-shaped cutout radius
CUT_Y = 50.3             # cutout centre (from face)
LOFT = 3.0
LIE = 74.0
BORE_D = 9.4
DENSITY = 7.93e-3        # g / mm^3  (SUS304)
CLUB_LEN = 34 * 25.4     # 34" putter

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection


def link(obj):
    col.objects.link(obj)
    return obj


def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def frame_pt(origin, U, V, W, u, v, w):
    return Vector(origin) + u * Vector(U) + v * Vector(V) + w * Vector(W)


def prism(name, pts, origin=(0, 0, 0), U=(1, 0, 0), V=(0, 0, 1), W=(0, 1, 0), d0=0.0, d1=1.0):
    """Extrude a closed 2D polygon (u,v) along W from d0 to d1."""
    bm = bmesh.new()
    a = [bm.verts.new(frame_pt(origin, U, V, W, u, v, d0)) for u, v in pts]
    b = [bm.verts.new(frame_pt(origin, U, V, W, u, v, d1)) for u, v in pts]
    n = len(pts)
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return mesh_obj(name, bm)


def circle(r, n=64, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]


def stadium(half, r, n=40):
    pts = []
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((half + r * math.cos(a), r * math.sin(a)))
    for i in range(n + 1):
        a = math.pi / 2 + math.pi * i / n
        pts.append((-half + r * math.cos(a), r * math.sin(a)))
    return pts


def rounded_rect(w, h, r, n=8):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def box(name, x0, x1, y0, y1, z0, z1):
    return prism(name, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], d0=y0, d1=y1)


def tube(name, p0, d, length, r0, r1, n=48, U=None):
    d = Vector(d).normalized()
    if U is None:
        U = d.orthogonal().normalized()
    V = d.cross(U)
    bm = bmesh.new()
    a = [bm.verts.new(Vector(p0) + r0 * (math.cos(t) * U + math.sin(t) * V)) for t in (2 * math.pi * i / n for i in range(n))]
    b = [bm.verts.new(Vector(p0) + d * length + r1 * (math.cos(t) * U + math.sin(t) * V)) for t in (2 * math.pi * i / n for i in range(n))]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return mesh_obj(name, bm)


def set_active(obj):
    for o in list(bpy.context.scene.objects):
        if o is not None:
            o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def boolean(target, cutter, op="DIFFERENCE", solver="EXACT", keep=False):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.solver = solver
    if cutter.type == "MESH" and cutter.name.startswith("SET_"):
        m.use_self = True
    m.object = cutter
    set_active(target)
    bpy.ops.object.modifier_apply(modifier=m.name)
    if not keep:
        bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def bevel(obj, width, segments=3, angle=40):
    m = obj.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = False
    set_active(obj)
    bpy.ops.object.modifier_apply(modifier=m.name)
    return obj


def join(objs, name):
    set_active(objs[0])
    for o in objs[1:]:
        o.select_set(True)
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def text_mesh(name, body, size, matrix, extrude=0.03, align_x="CENTER", spacing=1.0):
    cu = bpy.data.curves.new(name + "_crv", "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align_x
    cu.align_y = "CENTER"
    cu.space_line = spacing
    ob = link(bpy.data.objects.new(name + "_txt", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    out = link(bpy.data.objects.new(name, me))
    out.matrix_world = matrix
    set_active(out)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return out


def frame_matrix(origin, X, Y, Z):
    m = Matrix((Vector(X), Vector(Y), Vector(Z))).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def shade_smooth(obj, angle=35):
    set_active(obj)
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
    except Exception:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))


# ---------------------------------------------------------------- materials
def mat(name, color, metallic=0.0, rough=0.5, coat=0.0, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.08
    if image:
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image)
        m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        m.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            m.blend_method = "BLEND"
    return m


M_BLACK = mat("Black_CNC_Coat", (0.012, 0.012, 0.013), metallic=0.0, rough=0.36)
M_STEEL = mat("SUS304_Polished", (0.78, 0.77, 0.75), metallic=1.0, rough=0.18)
M_STEEL_DARK = mat("SUS304_Engraved", (0.08, 0.08, 0.08), metallic=0.8, rough=0.5)
M_PAINT = mat("White_Paintfill", (0.88, 0.88, 0.88), rough=0.45)
M_SHAFT = mat("Graphite_Shaft_Gloss", (0.006, 0.006, 0.007), rough=0.15)
M_FERRULE = mat("Ferrule_Black", (0.01, 0.01, 0.01), rough=0.3)
M_GRIP_W = mat("Grip_White", (0.82, 0.82, 0.8), rough=0.75)
M_GRIP_B = mat("Grip_Black", (0.015, 0.015, 0.015), rough=0.6)
M_LOGO = mat("Face_Logo_Decal", (1, 1, 1), rough=0.4, image=os.path.join(HERE, "textures", "gr_logo.png"))


def assign(obj, m):
    obj.data.materials.clear()
    obj.data.materials.append(m)


# ================================================================ HEAD
print("building head ...")
front = prism("face_bar", stadium(X_WING, R_WING, 48), origin=(0, 0, R_WING), d0=0.0, d1=BAR_T)
bevel(front, 1.0, 3, 30)

wings = []
for s in (-1, 1):
    w = prism(f"wing_{s}", circle(R_WING, 96), origin=(s * X_WING, 0, R_WING), d0=4.0, d1=WING_LEN)
    bevel(w, 0.8, 3, 30)
    wings.append(w)

web = box("web", -X_WING, X_WING, 6.0, WING_LEN - 3.0, 0.0, WEB_H)
head = front
head.name = "DP301_Head"
for part in (*wings, web):
    boolean(head, part, op="UNION")

# ball cutout (U-shape open to the back)
cut = join([
    prism("cut_c", circle(CUT_R, 96, 0, CUT_Y), U=(1, 0, 0), V=(0, 1, 0), W=(0, 0, 1), d0=-5, d1=40),
    box("cut_b", -CUT_R, CUT_R, CUT_Y, 100, -5, 40),
], "SET_cut")
boolean(head, cut)

# rear pockets + text area on the back wall of the face bar
zc = (WEB_H + HEAD_H) / 2 + 0.5
for s in (-1, 1):
    pk = prism(f"pocket_{s}", rounded_rect(11, 8, 1.6), origin=(s * 18.0, BAR_T, zc), d0=-1.2, d1=2.0)
    boolean(head, pk)

# diamond face milling: two families of grooves clipped to an inset stadium
print("milling face ...")
PITCH, ANG, GW, GD = 4.4, 28.0, 0.55, 0.35
grooves = []
for sgn in (-1, 1):
    a = math.radians(sgn * ANG)
    dirv = Vector((math.cos(a), 0, math.sin(a)))
    nrm = Vector((-math.sin(a), 0, math.cos(a)))
    for k in range(-16, 17):
        c = Vector((0, 0, R_WING)) + nrm * (k * PITCH)
        pts = [(-80, -GW / 2), (80, -GW / 2), (80, GW / 2), (-80, GW / 2)]
        g = prism(f"g{sgn}_{k}", pts, origin=c, U=dirv, V=nrm, W=(0, 1, 0), d0=-1.0, d1=GD)
        grooves.append(g)
gset = join(grooves, "SET_grooves")
clip = prism("SET_clip", stadium(X_WING, R_WING - 3.2, 48), origin=(0, 0, R_WING), d0=-2, d1=2)
boolean(gset, clip, op="INTERSECT")
gset.name = "SET_grooves"
boolean(head, gset)

# shaft bore (centre shafted, lie 74 deg toward heel)
lie = math.radians(LIE)
D_SHAFT = Vector((-math.cos(lie), 0, math.sin(lie)))
U_SHAFT = Vector((math.sin(lie), 0, math.cos(lie)))
ENTRY = Vector((0.0, BAR_T / 2, HEAD_H))
bore = tube("bore", ENTRY - D_SHAFT * 20, D_SHAFT, 30, BORE_D / 2, BORE_D / 2, 48)
boolean(head, bore)

# hollow wings (end weights screw into them) - bore radius solved for 395 g
def volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


BORE_Y0 = BAR_T + 1.0
v_solid = volume(head)
v_cap_shell = 2 * math.pi * (R_WING - 0.4) ** 2 * 3.5          # approx, refined later
L_hollow = WING_LEN - BORE_Y0
excess = v_solid + v_cap_shell - TARGET_G / DENSITY
R_IN = min(math.sqrt(max(excess, 0) / (2 * math.pi * (L_hollow - PLUG_LEN))), R_WING - 1.8)
print(f"wing bore radius solved: {R_IN:.2f} mm")
for s in (-1, 1):
    hb = prism(f"wingbore_{s}", circle(R_IN, 96), origin=(s * X_WING, 0, R_WING), d0=BORE_Y0, d1=WING_LEN + 1)
    boolean(head, hb)

# loft: lean the face back 3 deg (shear only the face-bar zone)
t = math.tan(math.radians(LOFT))


def loft_shear(obj):
    for v in obj.data.vertices:
        y, z = v.co.y, v.co.z
        if y < BAR_T:
            v.co.y = y + z * t * (BAR_T - y) / BAR_T


loft_shear(head)
shade_smooth(head, 35)
assign(head, M_BLACK)

# ---- end weights (polished steel caps with gear engraving + torx)
print("end caps ...")
caps = []
for s in (-1, 1):
    cx = s * X_WING
    cap = prism(f"cap_{s}", circle(R_WING - 0.4, 96), origin=(cx, 0, R_WING), d0=WING_LEN, d1=WING_LEN + 3.0)
    bevel(cap, 0.7, 3, 30)
    plug = prism(f"plug_{s}", circle(R_IN - 0.05, 96), origin=(cx, 0, R_WING), d0=WING_LEN - PLUG_LEN, d1=WING_LEN + 0.5)
    boolean(cap, plug, op="UNION")
    O, U, V, W = (cx, 0, R_WING), (1, 0, 0), (0, 0, 1), (0, 1, 0)
    gear = [(r * math.cos(a), r * math.sin(a)) for a, r in
            ((2 * math.pi * i / 160, 8.2 + 1.0 * math.tanh(3 * math.cos(8 * 2 * math.pi * i / 160)) / math.tanh(3)) for i in range(160))]
    outer = prism("g_out", [(u * 1.045, v * 1.045) for u, v in gear], O, U, V, W, WING_LEN + 2.6, WING_LEN + 4)
    inner = prism("g_in", [(u * 0.955, v * 0.955) for u, v in gear], O, U, V, W, WING_LEN + 2.5, WING_LEN + 4.1)
    boolean(outer, inner)
    boolean(cap, outer)
    holes = [prism(f"h{i}", circle(0.45, 16, 5.9 * math.cos(a), 5.9 * math.sin(a)), O, U, V, W, WING_LEN + 2.3, WING_LEN + 4)
             for i, a in enumerate(2 * math.pi * (i + 0.5) / 8 for i in range(8))]
    boolean(cap, join(holes, "SET_holes"))
    torx = [(r * math.cos(a), r * math.sin(a)) for a, r in
            ((2 * math.pi * i / 72, 1.9 + 0.45 * math.cos(6 * 2 * math.pi * i / 72)) for i in range(72))]
    boolean(cap, prism("torx", torx, O, U, V, W, WING_LEN + 1.0, WING_LEN + 4))
    ring = prism("ring", circle(3.6, 64), O, U, V, W, WING_LEN + 2.75, WING_LEN + 4)
    boolean(cap, join([ring], "ringcut"))
    shade_smooth(cap, 30)
    assign(cap, M_STEEL)
    caps.append(cap)

# ---- paint fill / decals
print("decals ...")
paint = []
# alignment line on the web
paint.append(box("align_line", -0.5, 0.5, BAR_T, CUT_Y - CUT_R + 0.3, WEB_H - 0.05, WEB_H + 0.03))
# GRAZR on the back wall, between the pockets (reads from behind)
paint.append(text_mesh("back_GRAZR", "GRAZR", 4.6,
                       frame_matrix((0, BAR_T + 0.005, zc), (-1, 0, 0), (0, 0, 1), (0, 1, 0)), extrude=0.02))
# sole engravings (paint-filled)
sole = lambda o, X: frame_matrix(o, X, Vector((0, 0, -1)).cross(Vector(X)), (0, 0, -1))
paint.append(text_mesh("sole_GRAZR", "GRAZR", 7.0, sole((0, 18.0, -0.01), (1, 0, 0)), extrude=0.02))
paint.append(text_mesh("sole_DP301", "DP-301", 3.6, sole((0, 24.6, -0.01), (1, 0, 0)), extrude=0.02))
paint.append(text_mesh("sole_heel", "100%CNC MILLED\nFORGED MODEL\nSTAINLESS\nSUS 304", 1.9,
                       sole((-33.5, 44.0, -0.01), (0, 1, 0)), extrude=0.02))
paint.append(text_mesh("sole_toe", "DUAL BALANCE\nW.T/395g\nLOFT/3°\nLIE/74°", 1.9,
                       sole((33.5, 44.0, -0.01), (0, 1, 0)), extrude=0.02))
paint_obj = join(paint, "DP301_Paintfill")
assign(paint_obj, M_PAINT)

# face logo decal (toe side), follows the loft
bm = bmesh.new()
L = 15.0
cxl, czl = X_WING - 3.5, R_WING
vs = [bm.verts.new((cxl + du, -0.06, czl + dv)) for du, dv in ((-L / 2, -L / 2 * 310 / 265), (L / 2, -L / 2 * 310 / 265), (L / 2, L / 2 * 310 / 265), (-L / 2, L / 2 * 310 / 265))]
f = bm.faces.new(vs)
uv = bm.loops.layers.uv.new()
for loop, c in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
    loop[uv].uv = c
me = bpy.data.meshes.new("logo")
bm.to_mesh(me)
bm.free()
logo = link(bpy.data.objects.new("DP301_FaceLogo", me))
loft_shear(logo)
assign(logo, M_LOGO)

# ================================================================ SHAFT + GRIP
print("shaft & grip ...")
ferrule = tube("DP301_Ferrule", ENTRY - D_SHAFT * 1.0, D_SHAFT, 7.0, 5.4, 5.0, 64, U=U_SHAFT)
bevel(ferrule, 0.6, 2, 30)
shade_smooth(ferrule)
assign(ferrule, M_FERRULE)

ground = ENTRY - D_SHAFT * (HEAD_H / math.sin(lie))   # where the shaft line meets the sole plane
butt = ground + D_SHAFT * CLUB_LEN
shaft_len = (butt - ENTRY).length + 18 - 4
shaft = tube("DP301_Shaft", ENTRY - D_SHAFT * 18, D_SHAFT, shaft_len, BORE_D / 2, 7.2, 64, U=U_SHAFT)
shade_smooth(shaft, 60)
assign(shaft, M_SHAFT)

GRIP_LEN = 265.0
g0 = butt - D_SHAFT * GRIP_LEN
V_SHAFT = D_SHAFT.cross(U_SHAFT)
FLAT = 0.84
ring_n, seg = 40, 64


def grip_r(tn):
    return 12.8 + 5.4 * tn


bm = bmesh.new()
rings = []
for i in range(ring_n + 1):
    tn = i / ring_n
    r = grip_r(tn)
    s = tn * GRIP_LEN
    dome = 0.0
    rr = r
    if tn > 0.97:  # rounded cap
        k = (tn - 0.97) / 0.03
        rr = r * math.sqrt(max(1 - k * k, 0.05))
    ring = []
    for j in range(seg):
        a = 2 * math.pi * j / seg
        u, v = rr * math.cos(a), rr * math.sin(a)
        u = min(u, FLAT * rr)          # flat front for the thumbs
        ring.append(bm.verts.new(g0 + D_SHAFT * (s + dome) + U_SHAFT * u + V_SHAFT * v))
    rings.append(ring)
bm.faces.new(list(reversed(rings[0])))
bm.faces.new(rings[-1])
for i in range(ring_n):
    for j in range(seg):
        k = (j + 1) % seg
        f = bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
        tn = (i + 0.5) / ring_n
        f.material_index = 1 if (tn < 0.05 or tn > 0.78) else 0
grip = mesh_obj("DP301_Grip", bm)
grip.data.materials.append(M_GRIP_W)
grip.data.materials.append(M_GRIP_B)
shade_smooth(grip, 50)

# GRAZR on the flat of the grip (reads downward, like the photo)
tm = 0.45
pos = g0 + D_SHAFT * (tm * GRIP_LEN) + U_SHAFT * (FLAT * grip_r(tm) + 0.01)
tilt = math.atan(FLAT * 5.4 / GRIP_LEN)
Xg = -D_SHAFT
Zg = (U_SHAFT * math.cos(tilt) - D_SHAFT * math.sin(tilt)).normalized()
Yg = Zg.cross(Xg)
gtxt = text_mesh("DP301_GripText", "GRAZR", 12.5, frame_matrix(pos, Xg, Yg, Zg), extrude=0.15)
assign(gtxt, M_GRIP_B)

# ================================================================ mass report
v_head = volume(head)
v_caps = sum(volume(c) for c in caps)
mass_head = (v_head + v_caps) * DENSITY
report = (f"head body volume {v_head/1000:.2f} cm^3, caps {v_caps/1000:.2f} cm^3\n"
          f"SUS304 head mass (body + caps) = {mass_head:.1f} g  (spec {TARGET_G:.0f} g)\n"
          f"wing bore radius {R_IN:.2f} mm (wall {R_WING-R_IN:.2f} mm), web height {WEB_H} mm\n")
print(report)

# ================================================================ assembly root (mm -> m)
root = link(bpy.data.objects.new("GRAZR_DP301", None))
for o in list(col.objects):
    if o is not root and o.type == "MESH":
        o.parent = root
root.scale = (0.001, 0.001, 0.001)
bpy.context.view_layer.update()

head_parts = [head, *caps]
all_parts = [o for o in col.objects if o.type == "MESH"]

# ================================================================ exports
print("exporting ...")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "dp301_putter.blend"))


def select(objs):
    for o in list(bpy.context.scene.objects):
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]


select(head_parts)
bpy.ops.wm.stl_export(filepath=os.path.join(OUT, "dp301_head.stl"), export_selected_objects=True,
                      global_scale=1000.0, apply_modifiers=True)
select(all_parts)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "dp301_putter.glb"), export_format="GLB",
                          use_selection=False, export_apply=True, export_yup=True)

with open(os.path.join(OUT, "mass_report.txt"), "w") as fh:
    fh.write(report)

# ================================================================ renders
if not RENDER:
    sys.exit(0)

print("rendering ...")
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(os.environ.get("SAMPLES", "96"))
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"

world = bpy.data.worlds.new("studio")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
grad = world.node_tree.nodes.new("ShaderNodeTexGradient")
coord = world.node_tree.nodes.new("ShaderNodeTexCoord")
ramp = world.node_tree.nodes.new("ShaderNodeValToRGB")
mapn = world.node_tree.nodes.new("ShaderNodeMapping")
mapn.inputs["Rotation"].default_value = (0, math.radians(-90), 0)
world.node_tree.links.new(coord.outputs["Generated"], mapn.inputs["Vector"])
world.node_tree.links.new(mapn.outputs["Vector"], grad.inputs["Vector"])
world.node_tree.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
ramp.color_ramp.elements[0].color = (0.01, 0.01, 0.012, 1)
ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
world.node_tree.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.35
scene.world = world


def area(name, loc, target, size, power):
    li = bpy.data.lights.new(name, "AREA")
    li.size = size
    li.energy = power
    ob = link(bpy.data.objects.new(name, li))
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


cam_data = bpy.data.cameras.new("cam")
cam_data.clip_start = 0.001
cam = link(bpy.data.objects.new("Camera", cam_data))
scene.camera = cam


def shot(name, loc, target, lens=85, lights=None, roll=0.0, head_only=False):
    only = os.environ.get("ONLY")
    if only and name not in only.split(","):
        return
    for o in (shaft, grip, gtxt, ferrule):
        o.hide_render = head_only
    cam.location = loc
    q = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y")
    cam.rotation_euler = (q @ Matrix.Rotation(math.radians(roll), 4, "Z").to_quaternion()).to_euler()
    cam_data.lens = lens
    for o in [o for o in col.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    for l in lights:
        area(*l)
    path = os.path.join(OUT, "renders", name + ".png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)            # flatten onto a light studio backdrop
    px = list(img.pixels)
    for i in range(0, len(px), 4):
        a = px[i + 3]
        for c in range(3):
            px[i + c] = px[i + c] * a + 0.94 * (1 - a)
        px[i + 3] = 1.0
    img.pixels = px
    img.save()
    bpy.data.images.remove(img)
    print("  ->", path)


hc = Vector((0, 0.035, 0.0125))  # head centre (m)
studio = lambda d=0.6: [
    ("key", hc + Vector((-0.25, -0.35, 0.45)) * d, hc, 0.6 * d, 6.0),
    ("fill", hc + Vector((0.4, 0.1, 0.25)) * d, hc, 0.8 * d, 2.5),
    ("rim", hc + Vector((0.0, 0.5, 0.3)) * d, hc, 0.5 * d, 5.0),
    ("top", hc + Vector((0, 0.03, 0.6)) * d, hc, 0.9 * d, 3.0),
]
os.makedirs(os.path.join(OUT, "renders"), exist_ok=True)
shot("01_hero", hc + Vector((0.20, -0.22, 0.16)), hc, 85, studio())
shot("02_face", hc + Vector((0, -0.40, 0.0)), hc + Vector((0, 0, 0)), 100, studio())
shot("03_top", hc + Vector((0, 0.0, 0.42)), hc, 85, studio(), head_only=True)
shot("04_back", hc + Vector((0, 0.40, 0.05)), hc, 85, studio())
shot("05_sole", hc + Vector((0, 0.0, -0.42)), hc, 85, studio(), roll=180, head_only=True)
mid = Vector((-0.12, 0.0, 0.42))
shot("06_full", mid + Vector((0.7, -2.4, 0.2)), mid, 55,
     [("key", mid + Vector((-0.8, -1.5, 1.2)), mid, 1.5, 60),
      ("fill", mid + Vector((1.2, -0.6, 0.4)), mid, 1.5, 22),
      ("rim", mid + Vector((0.2, 1.4, 0.8)), mid, 1.2, 40)])
print("done")
