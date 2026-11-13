"""GRAZR DP-301 putter - procedural Blender model (promo / render use).

Run:  python3 3d-model/build_dp301.py              (needs `pip install bpy==5.3.0 pillow`)
      python3 3d-model/build_dp301.py --no-render  (exports only)
  env SAMPLES=<n>   Cycles samples (default 96)
  env ONLY=a,b      render only the named shots

Geometry is authored in millimetres and parented to a root empty scaled
0.001, so the scene / glTF are in metres while STL exports stay in mm.

Coordinate frame (model space, mm) - right-handed putter:
  X = toe(-) -> heel(+), Y = face(0) -> back(+), Z = sole(0) -> up
  Viewed from the target the heel (shaft lean) is on the right.
All dimensions come from 3d-model/SPEC.md (owner measurements + ruler photos).
"""
import math
import os
import sys

import bpy  # noqa: E402  (must come before bmesh)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_textures as tex  # noqa: E402

OUT = HERE
TEXDIR = os.path.join(HERE, "textures")
RENDER = "--no-render" not in sys.argv

# ---------------------------------------------------------------- specs (mm)
FACE_LEN = 108.0          # face length == head width
HEAD_H = 25.0             # face height == wing diameter
R_WING = HEAD_H / 2
X_WING = FACE_LEN / 2 - R_WING      # wing axis |x|
BAR_T = 14.0              # face bar thickness (front -> back)
CAP_T = 2.0               # end weight thickness
DEPTH = 68.0              # face -> back of the end weights
WING_END = DEPTH - CAP_T  # back of the black wing body
WEB_H = 6.0               # centre plate height
LEDGE_H = 9.5             # raised ledge along the inner side of each wing
CUT_R = 21.0              # ball cutout (42 mm)
CUT_APEX = 25.0           # face -> front of the cutout
CUT_Y = CUT_APEX + CUT_R
LOFT = 3.0
LIE = 74.0
BORE_D = 9.4              # .370" shaft
DENSITY = 7.93e-3         # g / mm^3 (SUS304)
HEAD_G = 385.0            # head incl. end weights
CAP_G = 20.0              # each end weight
PLUG_LEN = 5.0
CLUB_LEN = 34 * 25.4
GRIP_LEN = tex.GRIP_LEN   # 270
FACE_BORDER = 2.0         # smooth border around the milled face

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection
FONT_B = bpy.data.fonts.load(os.path.join(tex.FONT_DIR, "Inter-Bold.otf"))


def link(obj):
    col.objects.link(obj)
    return obj


def mesh_obj(name, bm, recalc=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    if recalc:
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


def offset_poly(pts, d):
    """Offset a closed CCW polygon outward by d (vertex-normal offset)."""
    out = []
    n = len(pts)
    for i in range(n):
        (x0, y0), (x2, y2) = pts[i - 1], pts[(i + 1) % n]
        tx, ty = x2 - x0, y2 - y0
        L = math.hypot(tx, ty) or 1.0
        out.append((pts[i][0] + d * ty / L, pts[i][1] - d * tx / L))
    return out


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


def boolean(target, cutter, op="DIFFERENCE", keep=False, transfer=False):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.solver = "EXACT"
    if transfer:
        m.material_mode = "TRANSFER"
    if cutter.name.startswith("SET_"):
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


def frame_matrix(origin, X, Y, Z):
    m = Matrix((Vector(X), Vector(Y), Vector(Z))).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def text_mesh(name, body, size, matrix, extrude=0.02, align_x="CENTER", spacing=1.0, squash=1.0):
    cu = bpy.data.curves.new(name + "_crv", "FONT")
    cu.body = body
    cu.font = FONT_B
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
    out.matrix_world = matrix @ Matrix.Diagonal((squash, 1, 1, 1))
    set_active(out)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return out


def shade_smooth(obj, angle=35):
    set_active(obj)
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
    except Exception:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))


def volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


# ---------------------------------------------------------------- shaft line (needed by textures)
lie = math.radians(LIE)
D_SHAFT = Vector((math.cos(lie), 0, math.sin(lie)))       # up the shaft, leaning to the heel (+X)
N_FLAT = Vector((-math.sin(lie), 0, math.cos(lie)))       # grip flat / print side (faces the golfer's eyes)
V_SIDE = D_SHAFT.cross(N_FLAT)
ENTRY = Vector((0.0, BAR_T / 2, HEAD_H))
ground = ENTRY - D_SHAFT * (HEAD_H / math.sin(lie))
BUTT = ground + D_SHAFT * CLUB_LEN
G0 = BUTT - D_SHAFT * GRIP_LEN                              # bottom of the grip
S0 = ENTRY - D_SHAFT * 18.0                                 # shaft tip (inside the bore)
SHAFT_LEN = (BUTT - S0).length - 4.0
R_TIP, R_BUTT = BORE_D / 2, 6.3
X_GRIP = (G0 - S0).dot(D_SHAFT)


def shaft_r(x):
    return R_TIP + (R_BUTT - R_TIP) * x / SHAFT_LEN


print("textures ...")
tex.make_all(lambda v: shaft_r(X_GRIP - v))


# ---------------------------------------------------------------- materials
def mat(name, color, metallic=0.0, rough=0.5, coat=0.0, image=None, alpha_img=None, bump_img=None,
        bump_strength=0.3, milled=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.04
    if image:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(image)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha_img:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(alpha_img)
        nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    if bump_img:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(bump_img)
        t.image.colorspace_settings.name = "Non-Color"
        b = nt.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = bump_strength
        b.inputs["Distance"].default_value = 0.4
        nt.links.new(t.outputs["Color"], b.inputs["Height"])
        nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    if milled:                      # fine CNC fly-cut lines
        tc = nt.nodes.new("ShaderNodeTexCoord")
        w = nt.nodes.new("ShaderNodeTexWave")
        w.wave_type = "RINGS"
        w.inputs["Scale"].default_value = 0.9
        w.inputs["Distortion"].default_value = 0.0
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (-60.0, -140.0, 0.0)
        b = nt.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = milled
        b.inputs["Distance"].default_value = 0.02
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], w.inputs["Vector"])
        nt.links.new(w.outputs["Fac"], b.inputs["Height"])
        nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return m


T = lambda f: os.path.join(TEXDIR, f)
M_BLACK = mat("Black_CNC_Coat", (0.004, 0.004, 0.0045), rough=0.3)
M_STEEL = mat("SUS304_Polished", (0.92, 0.91, 0.89), metallic=1.0, rough=0.24)
M_ENGRAVE = mat("Engraving_Black", (0.003, 0.003, 0.003), rough=0.85)
M_PAINT = mat("White_Paintfill", (0.86, 0.86, 0.86), rough=0.45)
M_SHAFT = mat("Graphite_Shaft_GlossBlack", (0.004, 0.004, 0.0045), rough=0.12, coat=1.0)
M_SHAFT_PRINT = mat("Shaft_Print_White", (0.85, 0.85, 0.85), rough=0.2, coat=1.0, alpha_img=T("shaft_decal.png"))
M_FERRULE = mat("Ferrule_GlossBlack", (0.006, 0.006, 0.006), rough=0.15, coat=0.6)
M_GRIP = mat("Grip_Polyurethane", (1, 1, 1), rough=0.32, image=T("grip_albedo.png"), bump_img=T("grip_bump.png"), bump_strength=0.12)
M_GRIP_CAP = mat("Grip_Cap", (1, 1, 1), rough=0.6, image=T("grip_cap.png"), bump_img=T("grip_cap.png"), bump_strength=0.4)
M_MARK = mat("Decal_GR_Mark", (0.88, 0.88, 0.88), rough=0.4, alpha_img=T("mark_white.png"))
M_WORD = mat("Decal_GRAZR", (0.88, 0.88, 0.88), rough=0.4, alpha_img=T("wordmark_white.png"))


def assign(obj, m):
    obj.data.materials.clear()
    obj.data.materials.append(m)


def decal(name, material, img_aspect, center, X, Y, height, lift=0.02):
    """Image decal quad: X = right, Y = up (in the viewer's frame), normal = X x Y."""
    X, Y = Vector(X).normalized(), Vector(Y).normalized()
    Nn = X.cross(Y)
    c = Vector(center) + Nn * lift
    w = height * img_aspect
    bm = bmesh.new()
    vs = [bm.verts.new(c + X * (sx * w / 2) + Y * (sy * height / 2)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    for loop, q in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = q
    ob = mesh_obj(name, bm, recalc=False)
    assign(ob, material)
    return ob


# ================================================================ HEAD
print("building head ...")
front = prism("face_bar", stadium(X_WING, R_WING, 48), origin=(0, 0, R_WING), d0=0.0, d1=BAR_T)
bevel(front, 1.0, 3, 30)

parts = []
for s in (-1, 1):
    w = prism(f"wing_{s}", circle(R_WING, 96), origin=(s * X_WING, 0, R_WING), d0=4.0, d1=WING_END)
    bevel(w, 0.8, 3, 30)
    parts.append(w)
    ledge = box(f"ledge_{s}", min(s * 24.0, s * 31.0), max(s * 24.0, s * 31.0), BAR_T - 1.0, WING_END - 6.0, 0.0, LEDGE_H)
    bevel(ledge, 0.6, 2, 30)
    parts.append(ledge)
parts.append(box("web", -X_WING, X_WING, 6.0, WING_END - 3.0, 0.0, WEB_H))
head = front
head.name = "DP301_Head"
for part in parts:
    boolean(head, part, op="UNION")

# ball cutout (U-shape open to the back)
cut = join([
    prism("cut_c", circle(CUT_R, 128, 0, CUT_Y), U=(1, 0, 0), V=(0, 1, 0), W=(0, 0, 1), d0=-5, d1=40),
    box("cut_b", -CUT_R, CUT_R, CUT_Y, 100, -5, 40),
], "SET_cut")
boolean(head, cut)

# two rounded pockets on the back wall of the face bar, GRAZR between them
ZC_BACK = (WEB_H + HEAD_H) / 2
for s in (-1, 1):
    pk = prism(f"pocket_{s}", rounded_rect(10.0, 12.5, 2.0), origin=(s * 14.6, BAR_T, ZC_BACK), d0=-1.0, d1=2.0)
    boolean(head, pk)

# diamond face milling (+-32 deg, 8.3 x 5.2 mm diamonds) with a dash in every diamond
print("milling face ...")
PITCH, ANG, GW, GD = 4.4, 32.0, 0.5, 0.32
INNER = R_WING - FACE_BORDER - 0.35
cutters = []
for sgn in (-1, 1):
    a = math.radians(sgn * ANG)
    dirv = Vector((math.cos(a), 0, math.sin(a)))
    nrm = Vector((-math.sin(a), 0, math.cos(a)))
    for k in range(-16, 17):
        c = Vector((0, 0, R_WING)) + nrm * (k * PITCH)
        pts = [(-80, -GW / 2), (80, -GW / 2), (80, GW / 2), (-80, GW / 2)]
        cutters.append(prism(f"g{sgn}_{k}", pts, origin=c, U=dirv, V=nrm, W=(0, 1, 0), d0=-1.0, d1=GD))
sa, ca = math.sin(math.radians(ANG)), math.cos(math.radians(ANG))
dx, dz = PITCH / (2 * sa), PITCH / (2 * ca)
for n in range(-14, 15):
    for mz in range(-5, 6):
        if (n + mz) % 2 == 0:
            continue
        x, z = n * dx, mz * dz
        if abs(z) > INNER - 1.0 or abs(x) > X_WING + math.sqrt(max((INNER - 1.0) ** 2 - z * z, 0)) - 1.4:
            continue
        cutters.append(prism(f"dash_{n}_{mz}", rounded_rect(2.2, 0.5, 0.24, 3), origin=(x, 0, R_WING + z), d0=-1.0, d1=0.25))
gset = join(cutters, "SET_grooves")
clip = prism("SET_clip", stadium(X_WING, INNER, 48), origin=(0, 0, R_WING), d0=-2, d1=2)
boolean(gset, clip, op="INTERSECT")
gset.name = "SET_grooves"
boolean(head, gset)
# fine outline groove around the milled field
ring_o = prism("ring_o", stadium(X_WING, INNER + 0.35, 48), origin=(0, 0, R_WING), d0=-1, d1=0.3)
ring_i = prism("ring_i", stadium(X_WING, INNER, 48), origin=(0, 0, R_WING), d0=-2, d1=1)
boolean(ring_o, ring_i)
boolean(head, ring_o)

# shaft bore (centre shafted)
bore = tube("bore", ENTRY - D_SHAFT * 20, D_SHAFT, 30, BORE_D / 2, BORE_D / 2, 48)
boolean(head, bore)

# hollow wings (end weights screw in) - bore radius solved for the 385 g head spec
BORE_Y0 = BAR_T + 1.0
v_body_target = (HEAD_G - 2 * CAP_G) / DENSITY
excess = volume(head) - v_body_target
L_hollow = WING_END - BORE_Y0
R_IN = min(math.sqrt(max(excess, 0) / (2 * math.pi * L_hollow)), R_WING - 1.8)
print(f"wing bore radius solved: {R_IN:.2f} mm")
for s in (-1, 1):
    hb = prism(f"wingbore_{s}", circle(R_IN, 96), origin=(s * X_WING, 0, R_WING), d0=BORE_Y0, d1=WING_END + 1)
    boolean(head, hb)

# loft: lean the face back 3 deg (shear only the face-bar zone)
t_loft = math.tan(math.radians(LOFT))


def loft_shear(obj):
    for v in obj.data.vertices:
        y, z = v.co.y, v.co.z
        if y < BAR_T:
            v.co.y = y + z * t_loft * (BAR_T - y) / BAR_T


loft_shear(head)
shade_smooth(head, 35)
assign(head, M_BLACK)

# ---- end weights: polished SUS304 caps, engraved 6-lobe gear, 6 holes, ring, torx screw
print("end caps ...")
caps = []
gear = [(r * math.cos(a), r * math.sin(a)) for a, r in
        ((2 * math.pi * i / 240, 9.5 + 1.2 * math.tanh(3 * math.cos(6 * 2 * math.pi * i / 240)) / math.tanh(3)) for i in range(240))]
for s in (-1, 1):
    cx = s * X_WING
    O, U, V, W = (cx, 0, R_WING), (s * -1.0, 0, 0), (0, 0, 1), (0, 1, 0)
    cap = prism(f"cap_{s}", circle(R_WING - 0.3, 128), O, d0=WING_END, d1=DEPTH)
    bevel(cap, 0.45, 3, 30)
    plug = prism(f"plug_{s}", circle(R_IN - 0.05, 96), O, d0=WING_END - PLUG_LEN, d1=WING_END + 0.5)
    boolean(cap, plug, op="UNION")
    assign(cap, M_STEEL)
    face = DEPTH
    cuts = []
    outer = prism("g_out", offset_poly(gear, 0.2), O, U, V, W, face - 0.25, face + 1)
    inner = prism("g_in", offset_poly(gear, -0.2), O, U, V, W, face - 0.4, face + 1.1)
    boolean(outer, inner)
    cuts.append(outer)
    cuts += [prism(f"h{i}", circle(0.5, 20, 6.7 * math.cos(a), 6.7 * math.sin(a)), O, U, V, W, face - 0.6, face + 1)
             for i, a in enumerate(2 * math.pi * i / 6 + math.pi / 2 for i in range(6))]
    ro = prism("r_o", circle(5.35, 96), O, U, V, W, face - 0.25, face + 1)
    ri = prism("r_i", circle(5.05, 96), O, U, V, W, face - 0.4, face + 1.1)
    boolean(ro, ri)
    cuts.append(ro)
    torx = [(r * math.cos(a), r * math.sin(a)) for a, r in
            ((2 * math.pi * i / 72, 1.95 + 0.45 * math.cos(6 * 2 * math.pi * i / 72)) for i in range(72))]
    cuts.append(prism("torx", torx, O, U, V, W, face - 1.8, face + 1))
    cset = join(cuts, "SET_capcuts")
    assign(cset, M_ENGRAVE)
    boolean(cap, cset, transfer=True)
    shade_smooth(cap, 30)
    caps.append(cap)

# ---- paint fill / decals
print("decals ...")
paint = []
paint.append(box("align_line", -0.5, 0.5, BAR_T, CUT_APEX + 0.3, WEB_H - 0.05, WEB_H + 0.03))
sole_m = lambda o, X, squash=1.0: frame_matrix(o, X, Vector((0, 0, -1)).cross(Vector(X)), (0, 0, -1))
paint.append(text_mesh("sole_DP301", "DP-301", 4.4, sole_m((20.0, 18.8, -0.01), (1, 0, 0)), squash=0.95))
paint.append(text_mesh("sole_toe", "100%CNC MILLED\nFORGED MODEL\nSTAINLESS\nSUS 304", 2.2,
                       sole_m((-40.0, 38.0, -0.01), (1, 0, 0)), align_x="LEFT", squash=0.85))
paint.append(text_mesh("sole_heel", "DUAL BALANCE\nW.T/385g\nLOFT/3°\nLIE/74°", 2.2,
                       sole_m((40.0, 35.0, -0.01), (1, 0, 0)), align_x="RIGHT", squash=0.85))
paint_obj = join(paint, "DP301_Paintfill")
assign(paint_obj, M_PAINT)

decals = [
    # sole: hex mark + GRAZR wordmark (reads from below, tops toward the face)
    decal("DP301_Sole_Mark", M_MARK, tex.MARK_ASPECT, (-28.0, 9.5, 0.0), (1, 0, 0), (0, -1, 0), 16.0),
    decal("DP301_Sole_GRAZR", M_WORD, tex.WORD_ASPECT, (6.0, 11.0, 0.0), (1, 0, 0), (0, -1, 0), 7.4),
    # back wall: GRAZR between the pockets (reads from behind)
    decal("DP301_Back_GRAZR", M_WORD, tex.WORD_ASPECT, (0.0, BAR_T, ZC_BACK), (-1, 0, 0), (0, 0, 1), 3.0),
]
face_logo = decal("DP301_Face_Mark", M_MARK, tex.MARK_ASPECT, (39.0, 0.0, R_WING), (1, 0, 0), (0, 0, 1), 12.5, lift=0.06)
loft_shear(face_logo)
decals.append(face_logo)

# ================================================================ SHAFT + GRIP
print("shaft & grip ...")
ferrule = tube("DP301_Ferrule", ENTRY - D_SHAFT * 1.0, D_SHAFT, 6.0, 5.6, 5.0, 64, U=N_FLAT)
bevel(ferrule, 0.6, 2, 30)
shade_smooth(ferrule)
assign(ferrule, M_FERRULE)

shaft = tube("DP301_Shaft", S0, D_SHAFT, SHAFT_LEN, R_TIP, R_BUTT, 64, U=N_FLAT)
shade_smooth(shaft, 60)
assign(shaft, M_SHAFT)


def sleeve(name, v_len, lift, seg=96, step=4.0):
    """UV-mapped skin just above the shaft, from the grip bottom down v_len mm."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    rings = []
    nv = int(v_len / step)
    for i in range(nv + 1):
        v = v_len * i / nv
        x = X_GRIP - v
        c, r = S0 + D_SHAFT * x, shaft_r(x) + lift
        rings.append([bm.verts.new(c + r * (math.cos(a) * N_FLAT + math.sin(a) * V_SIDE))
                      for a in (-math.pi + 2 * math.pi * j / seg for j in range(seg))])
    for i in range(nv):
        for j in range(seg):
            k = (j + 1) % seg
            f = bm.faces.new((rings[i + 1][j], rings[i + 1][k], rings[i][k], rings[i][j]))
            uj, uk = j / seg, (j + 1) / seg
            vi, vi1 = 1 - i / nv, 1 - (i + 1) / nv
            for loop, q in zip(f.loops, ((uj, vi1), (uk, vi1), (uk, vi), (uj, vi))):
                loop[uvl].uv = q
    return mesh_obj(name, bm, recalc=False)


shaft_print = sleeve("DP301_Shaft_Print", tex.SHAFT_DECAL_LEN, 0.03)
shade_smooth(shaft_print, 60)
assign(shaft_print, M_SHAFT_PRINT)

# grip: round with a 20 mm flat (29 mm), arc-length UVs matching grip_albedo.png
SEG = 128
half = tex.GRIP_FLAT_HALF
dflat = math.sqrt(tex.GRIP_R ** 2 - half ** 2)
base = []
for j in range(SEG):
    a = -math.pi + 2 * math.pi * j / SEG
    u, v = tex.GRIP_R * math.cos(a), tex.GRIP_R * math.sin(a)
    if u > dflat:
        u, v = dflat, dflat * math.tan(a)
    base.append((u, v))
cum = [0.0]
for j in range(1, SEG + 1):
    (u0, v0), (u1, v1) = base[j - 1], base[j % SEG]
    cum.append(cum[-1] + math.hypot(u1 - u0, v1 - v0))
ucoord = [c / cum[-1] for c in cum]       # SEG+1 values, 0.5 at the flat centre


def grip_k(t):
    if t < 2.5:
        return (tex.GRIP_R - (2.5 - math.sqrt(max(2.5 ** 2 - (2.5 - t) ** 2, 0)))) / tex.GRIP_R
    kb = 1 - 0.045 * (t - 2.5) / (GRIP_LEN - 2.5)
    if t > 265.0:
        kb -= (4.0 - math.sqrt(max(16.0 - (t - 265.0) ** 2 * 16.0 / 25.0, 0))) / tex.GRIP_R
    return kb


ts = [0.0, 0.25, 0.7, 1.3, 2.0, 2.5, 4.0] + [5.0 * i for i in range(1, 53)] + [262.0, 264.0, 265.0, 266.5, 268.0, 269.0, 269.6, 270.0]
ts = sorted(set(ts))
bm = bmesh.new()
uvl = bm.loops.layers.uv.new()
rings = []
for t in ts:
    k = grip_k(t)
    c = BUTT - D_SHAFT * t
    rings.append([bm.verts.new(c + k * (u * N_FLAT + v * V_SIDE)) for u, v in base])
for i in range(len(ts) - 1):
    for j in range(SEG):
        k = (j + 1) % SEG
        f = bm.faces.new((rings[i + 1][j], rings[i + 1][k], rings[i][k], rings[i][j]))
        f.material_index = 0
        vi, vi1 = 1 - ts[i] / GRIP_LEN, 1 - ts[i + 1] / GRIP_LEN
        for loop, q in zip(f.loops, ((ucoord[j], vi1), (ucoord[j + 1], vi1), (ucoord[j + 1], vi), (ucoord[j], vi))):
            loop[uvl].uv = q
# butt cap: slightly domed fan with planar UVs (mark upright toward the flat)
top = bm.verts.new(BUTT + D_SHAFT * 0.5)
k0 = grip_k(0.0)
span = 2 * tex.GRIP_R
for j in range(SEG):
    k = (j + 1) % SEG
    f = bm.faces.new((rings[0][j], rings[0][k], top))
    f.material_index = 1
    for loop, (u, v) in zip(f.loops, (base[j], base[k], (0.0, 0.0))):
        kk = k0 if (u, v) != (0.0, 0.0) else 0.0
        loop[uvl].uv = (0.5 - kk * v / span, 0.5 + kk * u / span)
# bottom: annulus down to the shaft
inner = [bm.verts.new(G0 + (R_BUTT + 0.2) * (math.cos(a) * N_FLAT + math.sin(a) * V_SIDE))
         for a in (-math.pi + 2 * math.pi * j / SEG for j in range(SEG))]
for j in range(SEG):
    k = (j + 1) % SEG
    f = bm.faces.new((inner[j], inner[k], rings[-1][k], rings[-1][j]))
    for loop in f.loops:
        loop[uvl].uv = (0.5, 0.005)
grip = mesh_obj("DP301_Grip", bm)
grip.data.materials.append(M_GRIP)
grip.data.materials.append(M_GRIP_CAP)
shade_smooth(grip, 50)

# ================================================================ mass report
v_head = volume(head)
v_caps = sum(volume(c) for c in caps)
mass_body = v_head * DENSITY
report = (f"SUS304 head body {v_head/1000:.2f} cm^3 -> {mass_body:.1f} g\n"
          f"end weights 2 x {CAP_G:.0f} g (spec; modelled volume {v_caps/2000:.2f} cm^3 each)\n"
          f"head total = {mass_body + 2*CAP_G:.1f} g  (spec {HEAD_G:.0f} g)\n"
          f"wing bore radius {R_IN:.2f} mm (wall {R_WING-R_IN:.2f} mm), web {WEB_H} mm, ledge {LEDGE_H} mm\n"
          f"club length 34\", lie {LIE} deg, loft {LOFT} deg\n")
print(report)

# ================================================================ assembly root (mm -> m)
root = link(bpy.data.objects.new("GRAZR_DP301", None))
for o in list(col.objects):
    if o is not root and o.type == "MESH":
        o.parent = root
root.scale = (0.001, 0.001, 0.001)
bpy.context.view_layer.update()

for o in col.objects:
    if o.type == "MESH":
        o.data.name = o.name
head_parts = [head, *caps]
all_parts = [o for o in col.objects if o.type == "MESH"]

# ================================================================ exports
print("exporting ...")
bpy.ops.file.pack_all()
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
CLUB_ONLY = (shaft, shaft_print, grip, ferrule)


def look(loc, target, up=(0, 0, 1), roll=0.0):
    f = (Vector(target) - Vector(loc)).normalized()
    up = Vector(up)
    if abs(f.dot(up.normalized())) > 0.999:
        up = Vector((0, -1, 0)) if abs(f.z) > 0.9 else Vector((0, 0, 1))
    r = f.cross(up).normalized()
    u = r.cross(f)
    m = Matrix((r, u, -f)).transposed()
    return (m @ Matrix.Rotation(math.radians(roll), 3, "Z")).to_euler()


def shot(name, loc, target, lens=85, lights=None, up=(0, 0, 1), roll=0.0, head_only=False, res=(1600, 1200)):
    only = os.environ.get("ONLY")
    if only and name not in only.split(","):
        return
    for o in CLUB_ONLY:
        o.hide_render = head_only
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    cam.rotation_euler = look(loc, target, up, roll)
    cam_data.lens = lens
    for o in [o for o in col.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    for li in lights:
        area(*li)
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
    print("  ->", path, flush=True)


m_ = lambda v: Vector(v) * 0.001                 # mm -> m
hc = Vector((0, 0.034, 0.0125))
studio = lambda c=hc, d=0.6: [
    ("key", c + Vector((-0.25, -0.35, 0.45)) * d, c, 0.6 * d, 6.0),
    ("fill", c + Vector((0.4, 0.1, 0.25)) * d, c, 0.8 * d, 2.5),
    ("rim", c + Vector((0.0, 0.5, 0.3)) * d, c, 0.5 * d, 5.0),
    ("top", c + Vector((0, 0.03, 0.6)) * d, c, 0.9 * d, 1.8),
]
below = lambda L: [(n, Vector((p.x, p.y, -p.z)), t, sz, pw) for n, p, t, sz, pw in L]
os.makedirs(os.path.join(OUT, "renders"), exist_ok=True)
shot("01_hero", hc + Vector((-0.20, -0.22, 0.15)), hc + Vector((0.004, 0, 0)), 85, studio())
shot("02_face", hc + Vector((0, -0.40, 0.0)), hc, 100, studio())
shot("03_top", hc + Vector((0, 0.0, 0.42)), hc, 85, studio(), up=(0, 1, 0), head_only=True)
shot("04_back", hc + Vector((0, 0.40, 0.06)), hc, 85, studio())
shot("05_sole", hc + Vector((0, 0.0, -0.42)), hc, 85, below(studio()), up=(0, -1, 0), head_only=True)
caps_c = Vector((0, DEPTH, R_WING)) * 0.001
cap_t = Vector((-X_WING, DEPTH, R_WING)) * 0.001
shot("06_weights", cap_t + Vector((-0.06, 0.15, 0.05)), cap_t + Vector((0.012, -0.012, -0.002)), 85,
     studio(cap_t, 0.5) + [("back", cap_t + Vector((-0.05, 0.3, 0.12)), cap_t, 0.25, 4.0)])
gc = m_(BUTT - D_SHAFT * (GRIP_LEN / 2))
shot("07_grip", gc + m_(N_FLAT * 680 + V_SIDE * 290), gc, 85,
     [("key", gc + m_(N_FLAT * 500 + V_SIDE * -450 + D_SHAFT * 300), gc, 0.25, 7.0),
      ("fill", gc + m_(N_FLAT * 300 + V_SIDE * 600), gc, 0.35, 2.5),
      ("rim", gc + m_(N_FLAT * -300 + V_SIDE * 300 + D_SHAFT * 200), gc, 0.3, 6.0)],
     up=tuple(D_SHAFT), res=(1200, 1600))
lc = m_(G0 - D_SHAFT * 125)
shot("08_shaft", lc + m_(N_FLAT * 450 + V_SIDE * -60), lc, 85,
     [("key", lc + m_(N_FLAT * 300 + V_SIDE * -250 + D_SHAFT * 100), lc, 0.5, 8.0),
      ("fill", lc + m_(N_FLAT * 200 + V_SIDE * 300), lc, 0.5, 3.0)],
     up=tuple(-V_SIDE))
mid = Vector((0.112, 0.007, 0.415))
shot("09_full", mid + Vector((-0.75, -2.45, 0.25)), mid, 85,
     [("key", mid + Vector((-0.8, -1.5, 1.2)), mid, 1.5, 60),
      ("fill", mid + Vector((1.2, -0.6, 0.4)), mid, 1.5, 22),
      ("rim", mid + Vector((0.2, 1.4, 0.8)), mid, 1.2, 40)],
     res=(1200, 1600))
print("done")
