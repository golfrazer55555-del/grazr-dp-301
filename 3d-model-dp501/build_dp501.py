"""GRAZR DP-501 park golf club - procedural Blender model (promo / render use).

Run:  python3 3d-model-dp501/make_textures.py      (textures + outline.json from the design drawings)
      python3 3d-model-dp501/build_dp501.py         (model + exports + renders; needs `pip install bpy==5.3.0`)
      python3 3d-model-dp501/build_dp501.py --no-render
  env SAMPLES=<n> (default 96), ONLY=a,b (render only these shots)

Model space in mm (root empty scaled 0.001 -> metres), right-handed club, same frame as the DP-301 model:
  X = toe(-) -> heel(+), Y = face(0) -> back(+), Z = sole(0) -> up. The ball goes toward -Y.

Sources: owner drawings (head-*-design.jpg, shaft-design.jpg), photos, and the KSPO test report
(534 g, 85 cm, head height 56 mm, shaft 16 mm, face-sole 90 deg, shaft axis in the face plane).
"""
import json
import math
import os
import sys

import bpy  # noqa: E402
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
RENDER = "--no-render" not in sys.argv
OL = json.load(open(os.path.join(HERE, "outline.json")))

# ---------------------------------------------------------------- specs (mm)
HEAD_W, HEAD_D, HEAD_H = 106.0, 95.0, 56.0
FACE_T = 7.0                    # carbon face plate
SKIRT = 17.5                    # brass lower band height above the local sole (side drawing)
NOSE_Y = 81.0                   # brass nose starts here (top / side drawing)
CH_H, CH_V = 14.0, 10.0         # top edge chamfer (horizontal x vertical), face photo
R_BOT = 11.0                    # bottom edge round
LIE = 76.0                      # shaft lean toward the heel (photos); shaft axis stays in the face plane (report)
HOLE = OL["shaft_hole"] or (12.9, 30.0)
CLUB_LEN = 850.0                # sole plane -> grip end along the shaft (report: 85 cm)
GRIP_LEN = 350.0
SHAFT_R_TIP, SHAFT_R_MID, SHAFT_R_BUTT = 8.0, 9.2, 10.0
FERRULE_R, FERRULE_H = 10.0, 22.0
BAND = (200.0, 450.0)           # shaft graphic band, distance along the shaft from the sole plane

# side profile of the head (Y, Z), measured on the side drawings and scaled to 95 x 56 mm
TOP = [(0, 56.0), (48.3, 56.0), (53.4, 55.9), (58.5, 55.3), (63.6, 54.6), (68.7, 53.8), (73.8, 53.0),
       (78.9, 52.0), (84.0, 51.0), (89.1, 49.4), (95.0, 47.0)]
BOT = [(0, 0.0), (44.4, 0.0), (49.9, 2.5), (55.4, 4.5), (61.0, 6.6), (66.5, 8.9), (72.1, 11.1),
       (77.6, 13.4), (83.2, 15.9), (88.7, 18.5), (95.0, 21.5)]


def interp(tab, y):
    for (y0, z0), (y1, z1) in zip(tab, tab[1:]):
        if y <= y1:
            return z0 + (z1 - z0) * (y - y0) / max(y1 - y0, 1e-6)
    return tab[-1][1]


def half_width(y):
    """Half width of the top-view outline at depth y (from the drawing contour, symmetric)."""
    pts = OL["top"]
    xs = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
            xs.append(abs(x0 + (x1 - x0) * (y - y0) / (y1 - y0)))
    return max(xs) if xs else 0.0


# ---------------------------------------------------------------- reset / helpers
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection


def link(obj):
    col.objects.link(obj)
    return obj


def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def img(name, srgb=True):
    im = bpy.data.images.load(os.path.join(TEX, name), check_existing=True)
    if not srgb:
        im.colorspace_settings.name = "Non-Color"
    return im


def principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def tex_node(nt, image, uv="UVMap", extension="REPEAT", scale=None):
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = image
    t.extension = extension
    t.interpolation = "Cubic"
    u = nt.nodes.new("ShaderNodeUVMap")
    u.uv_map = uv
    if scale:
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = scale
        nt.links.new(u.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
    else:
        nt.links.new(u.outputs["UV"], t.inputs["Vector"])
    return t


def lacquer(name, decal=None):
    """Piano-black lacquer over maple; optional printed decal (RGBA, UV 'proj', clipped)."""
    m, nt, b = principled(name)
    b.inputs["Base Color"].default_value = (0.006, 0.006, 0.007, 1)
    b.inputs["Roughness"].default_value = 0.10
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.02
    if decal:
        t = tex_node(nt, img(decal), "proj", "CLIP")
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = (0.006, 0.006, 0.007, 1)
        nt.links.new(t.outputs["Alpha"], mix.inputs["Factor"])
        nt.links.new(t.outputs["Color"], mix.inputs["B"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
        # printed gold ink is a little metallic
        mt = nt.nodes.new("ShaderNodeMath")
        mt.operation = "MULTIPLY"
        mt.inputs[1].default_value = 0.35
        nt.links.new(t.outputs["Alpha"], mt.inputs[0])
        nt.links.new(mt.outputs["Value"], b.inputs["Metallic"])
    return m


def brass(name, engrave=False):
    """Brushed brass (grain front -> back). With engrave: sand-blasted logos + black DP-501 (UV 'proj')."""
    m, nt, b = principled(name)
    base = (0.70, 0.48, 0.19, 1)
    b.inputs["Base Color"].default_value = base
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.26
    b.inputs["Anisotropic"].default_value = 0.75
    tg = nt.nodes.new("ShaderNodeTangent")
    tg.direction_type = "UV_MAP"
    tg.uv_map = "proj"
    nt.links.new(tg.outputs["Tangent"], b.inputs["Tangent"])
    # fine brushing streaks
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 8.0
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "proj"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.02, 1.2, 1.0)       # long along U (the grain direction)
    nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.20
    rr.inputs["To Max"].default_value = 0.34
    nt.links.new(nz.outputs["Fac"], rr.inputs["Value"])
    rough = rr.outputs["Result"]
    if engrave:
        e = tex_node(nt, img("sole_engrave.png", False), "sole", "CLIP")
        k = tex_node(nt, img("sole_black.png", False), "sole", "CLIP")
        sp = nt.nodes.new("ShaderNodeTexNoise")          # sand-blast sparkle
        sp.inputs["Scale"].default_value = 900.0
        mixc = nt.nodes.new("ShaderNodeMix")
        mixc.data_type = "RGBA"
        mixc.inputs["A"].default_value = base
        mixc.inputs["B"].default_value = (0.88, 0.64, 0.24, 1)
        nt.links.new(e.outputs["Color"], mixc.inputs["Factor"])
        mixk = nt.nodes.new("ShaderNodeMix")
        mixk.data_type = "RGBA"
        mixk.inputs["B"].default_value = (0.01, 0.01, 0.01, 1)
        nt.links.new(mixc.outputs["Result"], mixk.inputs["A"])
        nt.links.new(k.outputs["Color"], mixk.inputs["Factor"])
        nt.links.new(mixk.outputs["Result"], b.inputs["Base Color"])
        mr = nt.nodes.new("ShaderNodeMix")
        mr.data_type = "FLOAT"
        nt.links.new(e.outputs["Color"], mr.inputs["Factor"])
        nt.links.new(rough, mr.inputs["A"])
        sr = nt.nodes.new("ShaderNodeMapRange")
        sr.inputs["To Min"].default_value = 0.42
        sr.inputs["To Max"].default_value = 0.62
        nt.links.new(sp.outputs["Fac"], sr.inputs["Value"])
        nt.links.new(sr.outputs["Result"], mr.inputs["B"])
        rough = mr.outputs["Result"]
        mm = nt.nodes.new("ShaderNodeMath")
        mm.operation = "SUBTRACT"
        mm.inputs[0].default_value = 1.0
        nt.links.new(k.outputs["Color"], mm.inputs[1])
        nt.links.new(mm.outputs["Value"], b.inputs["Metallic"])
        an = nt.nodes.new("ShaderNodeMath")              # engraving kills the brushing anisotropy
        an.operation = "MULTIPLY"
        an.inputs[0].default_value = 0.75
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(e.outputs["Color"], inv.inputs[1])
        nt.links.new(inv.outputs["Value"], an.inputs[1])
        nt.links.new(an.outputs["Value"], b.inputs["Anisotropic"])
        bp = nt.nodes.new("ShaderNodeBump")                # engraved = recessed
        bp.inputs["Strength"].default_value = 0.35
        bp.inputs["Distance"].default_value = 0.0003
        inv2 = nt.nodes.new("ShaderNodeMath")
        inv2.operation = "SUBTRACT"
        inv2.inputs[0].default_value = 1.0
        nt.links.new(e.outputs["Color"], inv2.inputs[1])
        nt.links.new(inv2.outputs["Value"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(rough, b.inputs["Roughness"])
    return m


def carbon_mat():
    m, nt, b = principled("DP501_CarbonFace")
    t = tex_node(nt, img("carbon_albedo.png"), "proj", "REPEAT", scale=(1 / 12.0, 1 / 12.0, 1))
    bt = tex_node(nt, img("carbon_bump.png", False), "proj", "REPEAT", scale=(1 / 12.0, 1 / 12.0, 1))
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.22
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.03
    b.inputs["Metallic"].default_value = 0.25
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.25
    nt.links.new(bt.outputs["Color"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def simple(name, color, metallic=0.0, rough=0.4, coat=0.0):
    m, nt, b = principled(name)
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.03
    return m


M_BLACK = lacquer("DP501_Lacquer")
M_TOP = lacquer("DP501_TopGraphic", "top_decal.png")
M_HEEL = lacquer("DP501_HeelLettering", "side_heel.png")
M_TOE = lacquer("DP501_ToeLettering", "side_toe.png")
M_CARBON = carbon_mat()
M_BRASS = brass("DP501_Brass")
M_SOLE = brass("DP501_SoleEngraved", engrave=True)
M_PIN = simple("DP501_BrassPin", (0.86, 0.66, 0.30, 1), 1.0, 0.18)
M_GOLD = simple("DP501_GoldRing", (0.95, 0.72, 0.28, 1), 1.0, 0.12)
HEAD_MATS = [M_BLACK, M_TOP, M_HEEL, M_TOE, M_CARBON, M_BRASS, M_SOLE]
I_BLACK, I_TOP, I_HEEL, I_TOE, I_CARBON, I_BRASS, I_SOLE = range(7)


# ================================================================ head (lofted cross-sections)
def section(y):
    """Closed XZ loop at depth y, from the bottom centre round counter-clockwise (seen from the front)."""
    w = max(half_width(min(max(y, 0.4), HEAD_D - 0.2)), 0.6)
    zb, zt = interp(BOT, y), interp(TOP, y)
    h = zt - zb
    ch, cv = min(CH_H, 0.34 * w), min(CH_V, 0.30 * h)
    r = min(R_BOT, 0.42 * w, 0.40 * h)
    zs = min(max(zb + SKIRT, zb + r + 0.5), zt - cv - 0.5)   # brass / lacquer line on the sides
    right = []
    for k in range(6):                                          # bottom, centre -> corner
        right.append((k / 6 * (w - r), zb))
    for k in range(9):                                          # bottom round
        a = -math.pi / 2 + k / 8 * math.pi / 2
        right.append((w - r + r * math.cos(a), zb + r + r * math.sin(a)))
    right.append((w, zs))
    for k in range(1, 4):
        right.append((w, zs + (zt - cv - zs) * k / 3))
    for k in range(1, 3):                                       # chamfer
        right.append((w - ch * k / 2, zt - cv + cv * k / 2))
    for k in range(1, 6):                                       # top, corner -> centre
        right.append(((w - ch) * (1 - k / 6), zt))
    loop = right + [(-x, z) for x, z in reversed(right[1:])]
    return loop, zb, zt, zs


ys = []
y = 0.0
while y < HEAD_D - 0.4:
    ys.append(y)
    y += 0.6 if y < 2 else (1.0 if y < FACE_T + 1 else 2.0)
for extra in (FACE_T, NOSE_Y):
    ys.append(extra)
ys = sorted(set(round(v, 3) for v in ys)) + [HEAD_D - 0.4, HEAD_D - 0.1]
bm = bmesh.new()
rings, meta = [], []
for y in ys:
    loop, zb, zt, zs = section(y)
    rings.append([bm.verts.new((x, y, z)) for x, z in loop])
    meta.append((zb, zs))
n = len(rings[0])
uv = bm.loops.layers.uv.new("proj")
uv_sole = bm.loops.layers.uv.new("sole")


def classify(cy, cz, nrm, zb_c, zs_c):
    if cy < FACE_T:
        return I_BLACK                 # the face plate's edges are lacquered; only its front shows carbon
    if cy > NOSE_Y or cz < zs_c - 0.05:
        return I_SOLE if nrm.z < -0.85 else I_BRASS
    if nrm.z > 0.3:
        return I_TOP
    if nrm.x > 0.6:
        return I_HEEL
    if nrm.x < -0.6:
        return I_TOE
    return I_BLACK


faces = []
for i in range(len(rings) - 1):
    for j in range(n):
        k = (j + 1) % n
        faces.append(bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j])))
front = bm.faces.new(list(reversed(rings[0])))
back = bm.faces.new(rings[-1])
bm.normal_update()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
yi = {round(y, 3): i for i, y in enumerate(ys)}
hd = OL["heel_text"]
td = OL["toe_text"]
for f in bm.faces:
    c = f.calc_center_median()
    if f is front:
        idx = I_CARBON
    elif f is back:
        idx = I_BRASS
    else:
        zb_c = interp(BOT, c.y)
        zs_c = min(max(zb_c + SKIRT, zb_c + min(R_BOT, 0.42 * half_width(c.y), 0.4 * (interp(TOP, c.y) - zb_c)) + 0.5),
                   interp(TOP, c.y) - min(CH_V, 0.3 * (interp(TOP, c.y) - zb_c)) - 0.5)
        idx = classify(c.y, c.z, f.normal, zb_c, zs_c)
    f.material_index = idx
    for l in f.loops:
        p = l.vert.co
        if idx == I_TOP:
            q = (p.y / HEAD_D, 1 - (p.x + HEAD_W / 2) / HEAD_W)
        elif idx == I_HEEL:
            q = ((p.y - (hd["y"] - hd["len"] / 2)) / hd["len"], (p.z - (hd["z"] - hd["h"] / 2)) / hd["h"])
        elif idx == I_TOE:
            q = (((td["y"] + td["len"] / 2) - p.y) / td["len"], (p.z - (td["z"] - td["h"] / 2)) / td["h"])
        elif idx == I_CARBON:
            q = (p.x, p.z) if f is front or abs(f.normal.y) > 0.5 else (p.y + p.x, p.z)
        else:                                      # brass: U along the grain (face -> back)
            q = (p.y, p.x + p.z * 0.3)
        l[uv].uv = q
        l[uv_sole].uv = ((p.x + HEAD_W / 2) / HEAD_W, 1 - p.y / HEAD_D)
head = mesh_obj("DP501_Head", bm)
for m in HEAD_MATS:
    head.data.materials.append(m)
for p in head.data.polygons:
    p.use_smooth = True
head.data.set_sharp_from_angle(angle=math.radians(28))
bev = head.modifiers.new("edges", "BEVEL")
bev.width = 0.6
bev.segments = 3
bev.limit_method = "ANGLE"
bev.angle_limit = math.radians(28)
bev.harden_normals = True

# ---- brass pins in the face (4, flush), positions from the face photo
pins = []
for px, pz in ((-24.0, 44.0), (24.0, 44.0), (-33.0, 14.5), (33.0, 14.5)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=3.7, radius2=3.7, depth=0.6,
                          matrix=Matrix.Translation((px, -0.05, pz)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    o = mesh_obj("DP501_FacePin", bm)
    o.data.materials.append(M_PIN)
    pins.append(o)

# ================================================================ shaft, ferrule, grip
D = Vector((math.cos(math.radians(LIE)), 0.0, math.sin(math.radians(LIE))))
FRONT = Vector((0, -1, 0))                   # printed side of the shaft faces the target (photos)
SIDE = D.cross(FRONT).normalized()
P0 = Vector((HOLE[0] - interp(TOP, HOLE[1]) / math.tan(math.radians(LIE)), HOLE[1], 0.0))
S_TOP = interp(TOP, HOLE[1]) / math.sin(math.radians(LIE))     # where the axis leaves the head top


def axis(s):
    return P0 + D * s


def tube(name, s0, s1, radius_at, seg=64, steps=None, mats=None, uv_fn=None, cap=False, phase=math.pi):
    """Ring j starts at the back (phase pi from FRONT), so v = j/seg puts the front at v = 0.5 and the seam at the back."""
    steps = steps or max(2, int((s1 - s0) / 4))
    bm = bmesh.new()
    lay = bm.loops.layers.uv.new("proj")
    rings = []
    for i in range(steps + 1):
        s = s0 + (s1 - s0) * i / steps
        r = radius_at(s)
        rings.append([bm.verts.new(axis(s) + r * (math.cos(a) * FRONT + math.sin(a) * SIDE))
                      for a in (phase + 2 * math.pi * j / seg for j in range(seg))])
    for i in range(steps):
        for j in range(seg):
            k = (j + 1) % seg
            f = bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
            if uv_fn:
                for l, (ii, jj) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                    l[lay].uv = uv_fn(s0 + (s1 - s0) * ii / steps, jj / seg)
    if cap:
        f = bm.faces.new(rings[-1])
        for l in f.loops:
            l[lay].uv = (0.5, 0.5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = mesh_obj(name, bm)
    for m in mats or []:
        o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def shaft_r(s):
    if s < BAND[0]:
        return SHAFT_R_TIP + (SHAFT_R_MID - SHAFT_R_TIP) * max(0.0, s - S_TOP) / (BAND[0] - S_TOP)
    return SHAFT_R_MID + (SHAFT_R_BUTT - SHAFT_R_MID) * min(1.0, (s - BAND[0]) / (CLUB_LEN - GRIP_LEN - BAND[0]))


# shaft material: gloss black + the wrap (U along the band from the grip end, V around with the front at 0.5)
m, nt, b = principled("DP501_Shaft")
b.inputs["Base Color"].default_value = (0.006, 0.006, 0.007, 1)
b.inputs["Roughness"].default_value = 0.12
b.inputs["Coat Weight"].default_value = 1.0
b.inputs["Coat Roughness"].default_value = 0.03
t = tex_node(nt, img("shaft_wrap.png"), "proj", "CLIP")
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = "RGBA"
mix.inputs["A"].default_value = (0.006, 0.006, 0.007, 1)
nt.links.new(t.outputs["Alpha"], mix.inputs["Factor"])
nt.links.new(t.outputs["Color"], mix.inputs["B"])
nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
mt = nt.nodes.new("ShaderNodeMath")
mt.operation = "MULTIPLY"
mt.inputs[1].default_value = 0.4
nt.links.new(t.outputs["Alpha"], mt.inputs[0])
nt.links.new(mt.outputs["Value"], b.inputs["Metallic"])
M_SHAFT = m

shaft = tube("DP501_Shaft", S_TOP - 4, CLUB_LEN - GRIP_LEN + 8, shaft_r, steps=220, mats=[M_SHAFT],
             uv_fn=lambda s, v: ((BAND[1] - s) / (BAND[1] - BAND[0]), v))

# ferrule: gloss black collar with a gold holographic band and a thin gold line
ferrule = tube("DP501_Ferrule", S_TOP - 3, S_TOP + FERRULE_H,
               lambda s: FERRULE_R - 0.6 * max(0.0, s - (S_TOP + FERRULE_H - 3)), steps=24,
               mats=[simple("DP501_FerruleBlack", (0.006, 0.006, 0.007, 1), 0, 0.1, 1.0)], cap=True)
ring = tube("DP501_FerruleRing", S_TOP + FERRULE_H - 9.5, S_TOP + FERRULE_H - 7.0,
            lambda s: FERRULE_R + 0.08, steps=2, mats=[M_GOLD])
ring2 = tube("DP501_FerruleLine", S_TOP + FERRULE_H - 5.4, S_TOP + FERRULE_H - 4.8,
             lambda s: FERRULE_R + 0.06, steps=1, mats=[M_GOLD])

# grip: rubber, pyramid texture, front panel + gold GRAZR (U around with the front at 0.5, V butt at top)
G0 = CLUB_LEN - GRIP_LEN


def grip_r(s):
    t = (s - G0) / GRIP_LEN
    return 11.5 + (14.0 - 11.5) * min(1.0, t * 1.4) - 0.6 * max(0.0, t - 0.97) / 0.03


m, nt, b = principled("DP501_Grip")
ta = tex_node(nt, img("grip_albedo.png"), "proj")
tb = tex_node(nt, img("grip_bump.png", False), "proj")
nt.links.new(ta.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.62
bp = nt.nodes.new("ShaderNodeBump")
bp.inputs["Strength"].default_value = 0.6
bp.inputs["Distance"].default_value = 0.0008
nt.links.new(tb.outputs["Color"], bp.inputs["Height"])
nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
M_GRIP = m
grip = tube("DP501_Grip", G0, CLUB_LEN - 0.5, grip_r, steps=200, mats=[M_GRIP],
            uv_fn=lambda s, v: (v, 1 - (CLUB_LEN - s) / GRIP_LEN))
# butt cap with the GR logo
bm = bmesh.new()
lay = bm.loops.layers.uv.new("proj")
c = axis(CLUB_LEN)
rr = grip_r(CLUB_LEN - 0.5)
vs = [bm.verts.new(c + rr * (math.cos(a) * FRONT + math.sin(a) * SIDE)) for a in (2 * math.pi * j / 64 for j in range(64))]
f = bm.faces.new(vs)
for l in f.loops:
    d = l.vert.co - c
    l[lay].uv = (0.5 + d.dot(SIDE) / (2 * rr), 0.5 + d.dot(-FRONT) / (2 * rr))
cap = mesh_obj("DP501_GripCap", bm)
m, nt, b = principled("DP501_GripCap")
tc = tex_node(nt, img("grip_cap.png"), "proj", "CLIP")
nt.links.new(tc.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.55
cap.data.materials.append(m)

# ================================================================ assembly root (mm -> m) + exports
root = link(bpy.data.objects.new("GRAZR_DP501", None))
for o in list(col.objects):
    if o is not root and o.type == "MESH":
        o.parent = root
        o.data.name = o.name
root.scale = (0.001, 0.001, 0.001)
bpy.context.view_layer.update()
print("head: %.0f x %.0f x %.0f mm, shaft enters at X=%.1f Y=%.1f, lie %.0f deg" % (HEAD_W, HEAD_D, HEAD_H, HOLE[0], HOLE[1], LIE))
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "dp501_parkgolf.blend"))
bpy.ops.export_scene.gltf(filepath=os.path.join(HERE, "dp501_parkgolf.glb"), export_format="GLB",
                          export_apply=True, export_yup=True)
if not RENDER:
    sys.exit(0)

# ================================================================ renders (approval stills)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(os.environ.get("SAMPLES", "96"))
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
world = bpy.data.worlds.new("studio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.055, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world
cam_data = bpy.data.cameras.new("cam")
cam_data.clip_start = 0.001
cam = link(bpy.data.objects.new("Camera", cam_data))
scene.camera = cam
CLUB_ONLY = (shaft, grip, cap)


def area(name, loc, target, size, power):
    li = bpy.data.lights.new(name, "AREA")
    li.size = size
    li.energy = power
    ob = link(bpy.data.objects.new(name, li))
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def look(loc, target, up=(0, 0, 1)):
    f = (Vector(target) - Vector(loc)).normalized()
    up = Vector(up)
    if abs(f.dot(up.normalized())) > 0.999:
        up = Vector((0, 1, 0))
    r = f.cross(up).normalized()
    u = r.cross(f)
    return Matrix((r, u, -f)).transposed().to_euler()


SITE = "--site" in sys.argv          # dark-studio stills for the website instead of the approval set


def shot(name, loc, target, lens, lights, up=(0, 0, 1), head_only=False, res=(1600, 1200), bg=0.94, folder="renders"):
    only = os.environ.get("ONLY")
    if only and name not in only.split(","):
        return
    for o in CLUB_ONLY:
        o.hide_render = head_only
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    cam.rotation_euler = look(loc, target, up)
    cam_data.lens = lens
    for o in [o for o in col.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    for li in lights:
        area(*li)
    os.makedirs(os.path.join(HERE, folder), exist_ok=True)
    path = os.path.join(HERE, folder, name + ".png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path)
    px = list(im.pixels)
    W, H = res
    for i in range(0, len(px), 4):
        a = px[i + 3]
        if bg < 0.5:                      # dark studio: faint radial glow behind the club, black edges
            k = i // 4
            x, y = (k % W) / W - 0.5, (k // W) / H - 0.42
            back = bg + 0.035 * max(0.0, 1.0 - (x * x + y * y) / 0.22)
        else:
            back = bg
        for ch in range(3):
            px[i + ch] = px[i + ch] * a + back * (1 - a)
        px[i + 3] = 1.0
    im.pixels = px
    im.save()
    bpy.data.images.remove(im)
    print("  ->", path, flush=True)


hc = Vector((0, 0.045, 0.028))
studio = lambda c=hc, d=0.7: [
    ("key", c + Vector((-0.30, -0.35, 0.45)) * d, c, 0.6 * d, 7.0),
    ("fill", c + Vector((0.45, 0.05, 0.25)) * d, c, 0.8 * d, 3.0),
    ("rim", c + Vector((0.0, 0.55, 0.35)) * d, c, 0.5 * d, 6.0),
    ("strip", c + Vector((-0.55, 0.25, 0.30)) * d, c, 0.15 * d, 3.0),   # narrow strip: crisp edge highlights
]
below = lambda L: [(n, Vector((p.x, p.y, -p.z)), tt, sz, pw * 0.6) for n, p, tt, sz, pw in L]
if SITE:
    dark = dict(bg=0.0, folder="site")
    key = lambda c, d=0.7: [
        ("key", c + Vector((-0.35, -0.30, 0.40)) * d, c, 0.35 * d, 9.0),
        ("rim", c + Vector((0.30, 0.55, 0.30)) * d, c, 0.25 * d, 10.0),
        ("rim2", c + Vector((-0.45, 0.45, 0.20)) * d, c, 0.25 * d, 6.0),
        ("strip", c + Vector((0.55, -0.20, 0.25)) * d, c, 0.12 * d, 3.5),
    ]
    shot("hero", hc + Vector((-0.30, -0.24, 0.13)), hc + Vector((0.035, 0.01, 0.010)), 70, key(hc),
         res=(1920, 1080), **dark)
    shot("hero_m", hc + Vector((-0.22, -0.30, 0.16)), hc + Vector((0.0, 0.0, 0.03)), 60, key(hc), res=(1080, 1350), **dark)
    mid = Vector((0.10, 0.03, 0.42))
    full_l = [("key", mid + Vector((-0.8, -1.5, 1.2)), mid, 1.0, 70), ("rim", mid + Vector((0.6, 1.2, 0.8)), mid, 0.8, 60),
              ("rim2", mid + Vector((-1.0, 0.8, 0.3)), mid, 0.8, 35)]
    shot("full", mid + Vector((-0.7, -2.2, 0.35)), mid, 85, full_l, res=(1200, 1500), **dark)
    shot("card", hc + Vector((-0.26, -0.28, 0.30)), hc + Vector((0.01, 0.0, 0.05)), 50, key(hc), res=(1200, 1500), **dark)
    back_c = Vector((0, 0.08, 0.025))
    shot("f_brass", back_c + Vector((0.16, 0.24, 0.10)), back_c, 85, key(back_c, 0.6), res=(1280, 960), head_only=True, **dark)
    shot("f_maple", hc + Vector((0.40, -0.10, 0.06)), hc, 85, key(hc), res=(1280, 960), head_only=True, **dark)
    sc = axis(BAND[0] + 125) * 0.001
    shot("f_shaft", sc + Vector((-0.05, -0.26, 0.05)), sc, 85, key(sc, 0.5), up=tuple(D), res=(1280, 960), **dark)
    shot("f_aim", hc + Vector((0.10, 0.05, 0.38)), hc, 70, key(hc), up=(-1, 0, 0), res=(1280, 960), **dark)
    shot("poster", hc + Vector((-0.30, -0.26, 0.20)), hc + Vector((0.0, 0.0, 0.03)), 60, key(hc), res=(1280, 720), **dark)
    print("done")
    sys.exit(0)

os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
shot("01_hero", hc + Vector((-0.24, -0.26, 0.20)), hc + Vector((0.004, 0, 0)), 85, studio())
shot("02_face", hc + Vector((0, -0.42, 0.02)), hc, 100, studio())
shot("03_top", hc + Vector((0, 0.0, 0.46)), hc, 85, studio(), up=(-1, 0, 0), head_only=True)
shot("04_back", hc + Vector((0.05, 0.42, 0.10)), hc, 85, studio())
shot("05_sole", hc + Vector((0, 0.0, -0.46)), hc, 85, below(studio()), up=(0, -1, 0), head_only=True)
shot("06_toe", hc + Vector((-0.42, 0.0, 0.05)), hc, 90, studio(), head_only=True)
shot("07_heel", hc + Vector((0.42, 0.0, 0.05)), hc, 90, studio(), head_only=True)
mid = Vector((0.10, 0.03, 0.42))
shot("08_full", mid + Vector((-0.8, -2.4, 0.3)), mid, 85,
     [("key", mid + Vector((-0.8, -1.5, 1.2)), mid, 1.5, 60), ("fill", mid + Vector((1.2, -0.6, 0.4)), mid, 1.5, 22),
      ("rim", mid + Vector((0.2, 1.4, 0.8)), mid, 1.2, 40)], res=(1200, 1600))
sc = axis(BAND[0] + 120) * 0.001
shot("09_shaft", sc + Vector((0.0, -0.34, 0.02)), sc, 85,
     [("key", sc + Vector((-0.3, -0.3, 0.2)), sc, 0.5, 8.0), ("fill", sc + Vector((0.3, -0.3, 0.0)), sc, 0.5, 3.0)],
     up=tuple(D), res=(1200, 1600))
print("done")
