"""GRAZR DP-501 park golf club - Blender model built from the owner's design drawings (dimensions: SPEC.md).

  python3 3d-model-dp501/make_textures.py
  python3 3d-model-dp501/build_dp501.py                 model + exports + approval renders (renders/)
  python3 3d-model-dp501/build_dp501.py --no-render
  python3 3d-model-dp501/build_dp501.py --ortho         orthographic check views vs the drawings (check/)
  env SAMPLES=<n> (default 128), ONLY=a,b

Model space in mm under a root empty scaled 0.001: X toe(-) -> heel(+), Y face(0) -> back(+), Z sole(0) -> up.

Head = one closed surface over the top-view outline: for every point, d = distance to the outline (sides and back;
the face edge excluded). The front cross-section profile (measured: detail-page face photo and the back photo agree)
gives the height above / below an edge line as functions of d; per Y row the profile is scaled and shifted so the
centre line follows the side drawing's top and bottom silhouettes exactly. So the model matches the top drawing,
the side drawing and the face / back cross-section at the same time.
"""
import math
import os
import sys

import bpy  # noqa: E402
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from scipy.interpolate import CubicSpline, PchipInterpolator
from scipy.optimize import brentq
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
RENDER = "--no-render" not in sys.argv
ORTHO = "--ortho" in sys.argv
SITE = "--site" in sys.argv               # dark-studio stills for the website (site/) instead of the approval set
PHOTO = "--photo" in sys.argv             # views matching the owner's photos (check/photo_*.png) for side-by-side checks
MATCH = "--match" in sys.argv             # the owner's photos' own cameras (check/photo_cams.json) -> check/match_*.png
WEB = "--web" in sys.argv                 # light model for the website's 3D viewer -> dp501_parkgolf.glb (no renders)
SAMPLES = int(os.environ.get("SAMPLES", "128"))

# ================================================================ measured shape (SPEC.md; the head is dp501_shape.py)
sys.path.insert(0, HERE)
import dp501_shape as S  # noqa: E402

HEAD_W, HEAD_D, HEAD_H = S.HEAD_W, S.HEAD_D, S.HEAD_H
FACE_T, NOSE_Y, TIP_Y = S.FACE_T, S.NOSE_Y, S.TIP_Y
K_Y = 95.0 / 94.4                        # side drawing length -> top drawing length
half_width = S.half_width

# brass pins in the face, measured on the owner's face photo (face 106 mm wide = 1440 px): x, z
PINS = [(-23.7, 41.9), (23.7, 41.9), (-33.0, 13.5), (33.0, 13.5)]
PIN_R = 3.3

# shaft / ferrule / grip (owner's measurements: grip 280, shaft 500 between ferrule and grip, ferrule 15 / 10 mm
# along the shaft on its long (toe) / short (heel) side; with the head these add up to the 850 mm club length)
HOLE = (12.9, 30.1)                      # where the shaft axis leaves the head top
LIE = math.radians(75.0)
CLUB_LEN = 850.0
GRIP_LEN = 280.0
FERRULE_R, FERRULE_LEN = 9.2, 12.5       # ferrule length along the axis at its centre line
BAND_FROM_TOP, BAND_H = 4.5, 2.1         # holographic band: centre 4.5 mm below the ferrule top, 2.1 mm wide
SHAFT_R0, SHAFT_R1 = 8.0, 9.75           # at the ferrule / under the grip
WRAP = (120.0, 465.0)                    # printed span of shaft_wrap.png (shaft_print.py), from the sole plane
PRINT_MID = 325.0                        # the knot (hex) of the shaft print, from the sole plane
SEAM = 0.16                              # glue line between the carbon face plate and the maple body


def head_normals(p, part):
    """Outward normals at head vertices p (n, 3). part: 0 top surface, 1 bottom surface, 2 on the outline (corner
    line), 3 the face plate's front edge row (y = 0), 4 the nose tip. Top / bottom normals come from central
    differences of the surface functions (steps kept inside the outline), the outline's from the outline itself."""
    x, y = p[:, 0], p[:, 1]
    n = np.zeros_like(p)
    for key, pid, sgn in (("zt", 0, 1.0), ("zb", 1, -1.0)):
        m = part == pid
        if not m.any():
            continue
        xm, ym = x[m], y[m]
        d = S.surfaces(xm, ym)["d"]
        h = np.clip(d / 4.0, 1e-5, 2e-3)
        hy = np.minimum(h, ym / 2.0)
        fx = (S.surfaces(xm + h, ym)[key] - S.surfaces(xm - h, ym)[key]) / (2 * h)
        fy = (S.surfaces(xm, ym + hy)[key] - S.surfaces(xm, ym - hy)[key]) / (2 * hy)
        n[m] = np.stack([-fx * sgn, -fy * sgn, np.full_like(fx, sgn)], 1)
    m = part == 2
    if m.any():
        k, dk = S.corner_squash(y[m])
        g = S.poly_dist(x[m] * k, y[m])[1]
        n[m] = np.stack([-g[:, 0] * k, -(g[:, 1] + g[:, 0] * x[m] * dk), np.zeros(m.sum())], 1)
    n[part == 3] = (0.0, -1.0, 0.0)
    n[part == 4] = (0.0, 1.0, 0.0)
    return n / np.linalg.norm(n, axis=1, keepdims=True)


# ================================================================ Blender helpers
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
    im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    return im


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes["Principled BSDF"]


def tex(nt, image, uv="proj", extension="CLIP", vector=None):
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = image
    t.extension = extension
    t.interpolation = "Cubic"
    if vector is None:
        u = nt.nodes.new("ShaderNodeUVMap")
        u.uv_map = uv
        vector = u.outputs["UV"]
    nt.links.new(vector, t.inputs["Vector"])
    return t


def world_vec(nt, v):
    """Object-space direction -> world space (for anisotropy tangents)."""
    c = node(nt, "ShaderNodeCombineXYZ", X=v[0], Y=v[1], Z=v[2])
    vt = nt.nodes.new("ShaderNodeVectorTransform")
    vt.vector_type = "VECTOR"
    vt.convert_from = "OBJECT"
    vt.convert_to = "WORLD"
    nt.links.new(c.outputs[0], vt.inputs[0])
    nm = nt.nodes.new("ShaderNodeVectorMath")
    nm.operation = "NORMALIZE"
    nt.links.new(vt.outputs[0], nm.inputs[0])
    return nm.outputs[0]


def mix_rgb(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    nt.links.new(fac, m.inputs["Factor"])
    for sock, v in (("A", a), ("B", b)):
        if isinstance(v, tuple):
            m.inputs[sock].default_value = v
        else:
            nt.links.new(v, m.inputs[sock])
    return m.outputs["Result"]


def mix_f(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "FLOAT"
    nt.links.new(fac, m.inputs["Factor"])
    for sock, v in (("A", a), ("B", b)):
        if isinstance(v, (int, float)):
            m.inputs[sock].default_value = v
        else:
            nt.links.new(v, m.inputs[sock])
    return m.outputs["Result"]


BLACK = (0.0055, 0.0055, 0.0062, 1)


def lacquer(name, decal=None):
    """Piano-black lacquer over maple; printed decal (gold / white ink) on UV 'proj'."""
    m, nt, b = principled(name)
    lacquer_into(nt, b, decal)
    return m


def lacquer_into(nt, b, decal=None):
    b.inputs["Base Color"].default_value = BLACK
    b.inputs["Roughness"].default_value = 0.12
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.012
    if decal:
        t = tex(nt, img(decal))
        nt.links.new(mix_rgb(nt, t.outputs["Alpha"], BLACK, t.outputs["Color"]), b.inputs["Base Color"])
        # gold ink is a metallic print, white ink is plain
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], sep.inputs[0])
        gold = nt.nodes.new("ShaderNodeMath")
        gold.operation = "SUBTRACT"
        nt.links.new(sep.outputs[0], gold.inputs[0])
        nt.links.new(sep.outputs[2], gold.inputs[1])          # r - b: high for gold ink, ~0 for white
        k = nt.nodes.new("ShaderNodeMath")
        k.operation = "MULTIPLY"
        k.use_clamp = True
        k.inputs[1].default_value = 2.0
        nt.links.new(gold.outputs[0], k.inputs[0])
        km = nt.nodes.new("ShaderNodeMath")
        km.operation = "MULTIPLY"
        nt.links.new(k.outputs[0], km.inputs[0])
        nt.links.new(t.outputs["Alpha"], km.inputs[1])
        nt.links.new(mix_f(nt, km.outputs[0], 0.0, 0.55), b.inputs["Metallic"])
        nt.links.new(mix_f(nt, t.outputs["Alpha"], 0.12, 0.3), b.inputs["Roughness"])


# yellow brushed brass: rendered with the sole photos' cameras (141, 144), the plain plate matches the photos'
# chroma and hue (Lab C 24.9 / 25.2, hue 88.3 / 88.5 deg); the earlier (0.62, 0.40, 0.10) read too deep and orange
BRASS = (0.64, 0.47, 0.15, 1)
# glitter in the sole engraving: flake scale (1/mm), darkest flake shade, normal tilt, flake roughness, colour.
# A richer gold than the plate as on the photos, with a gentle sparkle (half the earlier flake contrast)
GLIT = dict(scale=10.5, shade=0.80, tilt=0.42, rough=(0.14, 0.30), color=(0.80, 0.60, 0.10, 1))
if os.environ.get("BRASS"):                  # calibration: BRASS=r,g,b  GLIT=scale,shade,tilt,rmin,rmax,r,g,b
    BRASS = tuple(map(float, os.environ["BRASS"].split(","))) + (1,)
if os.environ.get("GLIT"):
    _g = list(map(float, os.environ["GLIT"].split(",")))
    GLIT = dict(scale=_g[0], shade=_g[1], tilt=_g[2], rough=(_g[3], _g[4]), color=tuple(_g[5:8]) + (1,))


def brass(name, engraved=False, rough_range=(0.22, 0.32)):
    """Brushed brass, grain along X (toe-heel). Engraved: recessed logos filled with gold glitter (photos), dark rim
    round them, black DP-501; textures on UV 'sole' (planar from below)."""
    m, nt, b = principled(name)
    brass_into(nt, b, engraved, rough_range)
    return m


def brass_into(nt, b, engraved=False, rough_range=(0.22, 0.32)):
    b.inputs["Base Color"].default_value = BRASS
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.2
    b.inputs["Anisotropic"].default_value = 0.65
    nt.links.new(world_vec(nt, (1, 0, 0)), b.inputs["Tangent"])
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.002, 9.0, 9.0)          # object space is mm: fine hairlines along X
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    nz = node(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=12.0, Roughness=0.7)
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    hair = node(nt, "ShaderNodeBump", Strength=0.12, Distance=0.00002)          # visible brushing as on the photos
    nt.links.new(nz.outputs["Fac"], hair.inputs["Height"])
    normal = hair.outputs["Normal"]
    rough = node(nt, "ShaderNodeMapRange", **{"From Min": 0.3, "From Max": 0.7, "To Min": rough_range[0],
                                              "To Max": rough_range[1]})
    nt.links.new(nz.outputs["Fac"], rough.inputs["Value"])
    rough = rough.outputs["Result"]
    color = BRASS
    metal = None
    aniso = None
    if engraved:
        e = tex(nt, img("sole_engrave.png", False), "sole")
        k = tex(nt, img("sole_black.png", False), "sole")
        r_ = tex(nt, img("sole_rings.png", False), "sole")
        # gold glitter in the engraving (photos): flakes ~0.1 mm, each its own tilt and shade, a gentle twinkle
        spark = node(nt, "ShaderNodeTexVoronoi", Scale=GLIT["scale"], Randomness=1.0)
        spark.feature = "F1"
        nt.links.new(coord.outputs["Object"], spark.inputs["Vector"])
        flake = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(spark.outputs["Color"], flake.inputs[0])
        shade = node(nt, "ShaderNodeMapRange", **{"To Min": GLIT["shade"], "To Max": 1.0})
        nt.links.new(flake.outputs[0], shade.inputs["Value"])
        glit = nt.nodes.new("ShaderNodeMix")
        glit.data_type = "RGBA"
        glit.blend_type = "MULTIPLY"
        glit.inputs["Factor"].default_value = 1.0
        glit.inputs[6].default_value = GLIT["color"]                       # glitter gold
        nt.links.new(shade.outputs["Result"], glit.inputs[7])
        color = mix_rgb(nt, e.outputs["Color"], BRASS, glit.outputs[2])
        color = mix_rgb(nt, r_.outputs["Color"], color, (0.05, 0.03, 0.006, 1))     # engraving rim: dark side wall
        color = mix_rgb(nt, k.outputs["Color"], color, (0.012, 0.012, 0.012, 1))
        sr = node(nt, "ShaderNodeMapRange", **{"To Min": GLIT["rough"][0], "To Max": GLIT["rough"][1]})  # shiny flakes
        nt.links.new(flake.outputs[1], sr.inputs["Value"])
        rough = mix_f(nt, e.outputs["Color"], rough, sr.outputs["Result"])
        rough = mix_f(nt, k.outputs["Color"], rough, 0.45)
        metal = mix_f(nt, k.outputs["Color"], 1.0, 0.0)
        aniso = mix_f(nt, e.outputs["Color"], 0.65, 0.0)
        # engraving is recessed: bump from (1 - mask); sparkle grains on the blasted floor
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        both = nt.nodes.new("ShaderNodeMath")
        both.operation = "MAXIMUM"
        nt.links.new(e.outputs["Color"], both.inputs[0])
        nt.links.new(r_.outputs["Color"], both.inputs[1])
        nt.links.new(both.outputs[0], inv.inputs[1])
        eb = node(nt, "ShaderNodeBump", Strength=0.6, Distance=0.00012)
        nt.links.new(inv.outputs[0], eb.inputs["Height"])
        nt.links.new(normal, eb.inputs["Normal"])
        # each flake tilts the normal its own way (random cell colour -> vector), only inside the engraving
        tilt = nt.nodes.new("ShaderNodeVectorMath")
        tilt.operation = "SUBTRACT"
        nt.links.new(spark.outputs["Color"], tilt.inputs[0])
        tilt.inputs[1].default_value = (0.5, 0.5, 0.5)
        sc = nt.nodes.new("ShaderNodeVectorMath")
        sc.operation = "SCALE"
        nt.links.new(tilt.outputs[0], sc.inputs[0])
        sc.inputs["Scale"].default_value = GLIT["tilt"]
        add = nt.nodes.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        nt.links.new(eb.outputs["Normal"], add.inputs[0])
        nt.links.new(sc.outputs[0], add.inputs[1])
        nrm = nt.nodes.new("ShaderNodeVectorMath")
        nrm.operation = "NORMALIZE"
        nt.links.new(add.outputs[0], nrm.inputs[0])
        nmix = nt.nodes.new("ShaderNodeMix")
        nmix.data_type = "VECTOR"
        nt.links.new(e.outputs["Color"], nmix.inputs["Factor"])
        nt.links.new(eb.outputs["Normal"], nmix.inputs[4])
        nt.links.new(nrm.outputs[0], nmix.inputs[5])
        normal = nmix.outputs[1]
    if isinstance(color, tuple):
        b.inputs["Base Color"].default_value = color
    else:
        nt.links.new(color, b.inputs["Base Color"])
    nt.links.new(rough if not isinstance(rough, float) else rough, b.inputs["Roughness"])
    nt.links.new(normal, b.inputs["Normal"])
    if metal is not None:
        nt.links.new(metal, b.inputs["Metallic"])
    if aniso is not None:
        nt.links.new(aniso, b.inputs["Anisotropic"])


def mnode(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def carbon_mat():
    """Plain-weave carbon under clear coat, as on the real face: the weave's shade comes from the owner's face photo
    (folded over the measured lattice), navy black; each tow with its own anisotropic sheen along its fibres and a
    light bump from the rounded tows; tile 4.33 x 4.22 mm."""
    m, nt, b = principled("DP501_CarbonFace")
    t = tex(nt, img("carbon.png", False), "proj", "REPEAT")
    sh = tex(nt, img("carbon_shade.png", False), "proj", "REPEAT")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t.outputs["Color"], sep.inputs[0])
    warp, height = sep.outputs[0], sep.outputs[1]
    col = nt.nodes.new("ShaderNodeMix")
    col.data_type = "RGBA"
    col.blend_type = "MULTIPLY"
    col.inputs["Factor"].default_value = 1.0
    col.inputs[6].default_value = (0.135, 0.145, 0.19, 1)            # navy black at shade 1
    nt.links.new(sh.outputs["Color"], col.inputs[7])
    nt.links.new(col.outputs[2], b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 0.3
    nt.links.new(mix_f(nt, warp, 0.40, 0.30), b.inputs["Roughness"])
    b.inputs["Anisotropic"].default_value = 0.8
    tan = nt.nodes.new("ShaderNodeMix")
    tan.data_type = "VECTOR"
    nt.links.new(warp, tan.inputs["Factor"])
    nt.links.new(world_vec(nt, (0, 0, 1)), tan.inputs[4])
    nt.links.new(world_vec(nt, (1, 0, 0)), tan.inputs[5])
    nt.links.new(tan.outputs[1], b.inputs["Tangent"])
    bp = node(nt, "ShaderNodeBump", Strength=0.2, Distance=0.0002)
    nt.links.new(height, bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.045
    return m


def simple(name, color, metallic=0.0, rough=0.4, coat=0.0):
    m, nt, b = principled(name)
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.015
    return m


def holo_band():
    """Holographic gold glitter band on the ferrule."""
    m, nt, b = principled("DP501_HoloBand")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    vor = node(nt, "ShaderNodeTexVoronoi", Scale=2.2)
    nt.links.new(coord.outputs["Object"], vor.inputs["Vector"])
    hue = node(nt, "ShaderNodeHueSaturation", Hue=0.5, Saturation=1.0, Value=1.0)
    hue.inputs["Color"].default_value = (0.95, 0.72, 0.28, 1)
    shift = node(nt, "ShaderNodeMapRange", **{"To Min": 0.42, "To Max": 0.62})
    nt.links.new(vor.outputs["Color"], shift.inputs["Value"])
    nt.links.new(shift.outputs["Result"], hue.inputs["Hue"])
    nt.links.new(hue.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.18
    bp = node(nt, "ShaderNodeBump", Strength=0.6, Distance=0.00005)
    nt.links.new(vor.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


M_LACQ = lacquer("DP501_Lacquer")
M_TOP = lacquer("DP501_TopGraphic", "top_decal.png")
M_HEEL = lacquer("DP501_HeelLettering", "side_heel.png")
M_TOE = lacquer("DP501_ToeLettering", "side_toe.png")
M_CARBON = carbon_mat()
M_BRASS = brass("DP501_Brass")
M_SOLE = brass("DP501_SoleEngraved", engraved=True)
M_PIN = brass("DP501_FacePin", rough_range=(0.32, 0.42))     # brushed like the photo's pins, a little more satin
M_SEAM = simple("DP501_FacePlateSeam", (0.002, 0.002, 0.002, 1), 0.0, 0.55)
HEAD_MATS = [M_LACQ, M_TOP, M_HEEL, M_TOE, M_CARBON, M_BRASS, M_SOLE, M_SEAM]
I_LACQ, I_TOP, I_HEEL, I_TOE, I_CARBON, I_BRASS, I_SOLE, I_SEAM = range(8)

# ================================================================ head surface
# rows: 3 deg steps over the face plate's 1 mm front round, 0.35 mm along the body, 0.1 mm over the nose; rows sit
# exactly on the face plate seam and on the brass nose boundary, so those material borders are clean edges
# (--web: the same rows and columns, only sparser)
_phi = np.radians(np.arange(0.0, 90.0, 10.0 if WEB else 3.0))
rows = np.concatenate([S.FRONT_R * (1 - np.cos(_phi)), [1.25, 1.75, 2.5], np.arange(3.1, 86.0, 1.1 if WEB else 0.35),
                       np.arange(86.0, TIP_Y - 0.15, 0.3 if WEB else 0.1), [TIP_Y - 0.1, TIP_Y - 0.06, TIP_Y - 0.03, TIP_Y - 0.012]])
rows = np.unique(np.round(np.concatenate([rows, [FACE_T - SEAM, FACE_T + SEAM, NOSE_Y, 41.3 * K_Y, 42.7 * K_Y]]), 6))
rows = rows[~np.isclose(rows, FACE_T)]
NO, NI = (22, 24) if WEB else (60, 64)    # top: columns per side on the chamfer (outline -> upper crease), crown
NW, NL = (18, 24) if WEB else (48, 64)    # bottom: on the side wall (outline -> lower crease), sole / lower chamfer


def _crease(y, w, inner_minus_outer):
    """|x| of the crease on a row: where the inner part (crown / sole) stops being the one the smooth min / max
    picks, going out from the centre line. 0 if the outer part (chamfer / wall) holds the whole row."""
    xx = np.linspace(0.0, w * 0.99999, 1500)
    g = inner_minus_outer(S.surfaces(xx, np.full_like(xx, y)))
    if g[0] <= 0:
        return 0.0
    out = np.nonzero(g <= 0)[0]
    if len(out) == 0:
        return w
    i = out[0] - 1
    return float(xx[i] + g[i] * (xx[i + 1] - xx[i]) / (g[i] - g[i + 1]))


def _columns(w, xc, n_out, n_in):
    """x positions across a row: outline -> crease (clustered at the outline, where the corner round turns fast),
    crease -> centre line, mirrored. 2 * (n_out + n_in) + 1 points from -w to +w."""
    t = np.linspace(0.0, 1.0, n_out + 1)
    outer = w - (w - xc) * t ** 2
    inner = xc * (1 - np.linspace(0.0, 1.0, n_in + 1))[1:]
    half = np.concatenate([outer, inner])
    return np.concatenate([-half, half[::-1][1:]])


bm = bmesh.new()
top_rows, bot_rows, vpart = [], [], {}
for y in rows:
    w = float(half_width(y))
    xu = _crease(y, w, lambda r: r["cham"] - r["crown"])   # the min picks the crown inside the upper crease
    xl = _crease(y, w, lambda r: r["lower"] - r["wall"])   # the max picks the sole inside the lower crease
    xt = _columns(w, xu if xu < w else 0.0, NO, NI)
    xb = _columns(w, xl if xl < w else 0.0, NW, NL)
    zt = S.surfaces(xt, np.full_like(xt, y))["zt"]
    zb = S.surfaces(xb, np.full_like(xb, y))["zb"]
    zt[0] = zt[-1] = zb[0] = zb[-1] = float(S.zc_line(y)) * (1 - 2 * float(S.front_round(y)) / HEAD_H) \
        + 28.0 * 2 * float(S.front_round(y)) / HEAD_H
    tr = [bm.verts.new((float(x), float(y), float(z))) for x, z in zip(xt, zt)]
    br = [tr[0]] + [bm.verts.new((float(x), float(y), float(z))) for x, z in zip(xb[1:-1], zb[1:-1])] + [tr[-1]]
    front_row = y == rows[0]
    for v in tr:
        vpart[v] = 3 if front_row else 0
    for v in br[1:-1]:
        vpart[v] = 3 if front_row else 1
    vpart[tr[0]] = vpart[tr[-1]] = 3 if front_row else 2
    top_rows.append(tr)
    bot_rows.append(br)
tip = bm.verts.new((0.0, TIP_Y, float(S.zc_line(TIP_Y))))
vpart[tip] = 4
NT, NB = len(top_rows[0]), len(bot_rows[0])
seg = {}                                           # face -> ("cham" | "crown" | "wall" | "lower")
for i in range(len(rows) - 1):
    for j in range(NT - 1):
        f = bm.faces.new((top_rows[i][j], top_rows[i + 1][j], top_rows[i + 1][j + 1], top_rows[i][j + 1]))
        seg[f] = "cham" if (j < NO or j >= NT - 1 - NO) else "crown"
    for j in range(NB - 1):
        f = bm.faces.new((bot_rows[i][j + 1], bot_rows[i + 1][j + 1], bot_rows[i + 1][j], bot_rows[i][j]))
        seg[f] = "wall" if (j < NW or j >= NB - 1 - NW) else "lower"
for j in range(NT - 1):
    seg[bm.faces.new((top_rows[-1][j], tip, top_rows[-1][j + 1]))] = "cham"
for j in range(NB - 1):
    seg[bm.faces.new((bot_rows[-1][j + 1], tip, bot_rows[-1][j]))] = "wall"
front = bm.faces.new([top_rows[0][j] for j in range(NT - 1, -1, -1)] + [bot_rows[0][j] for j in range(1, NB - 1)])
seg[front] = "front"
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # outward, before the normals decide the materials
bm.normal_update()
HB = (12.0, 54.0, 22.0, 40.0)        # = make_textures.HEEL_BOX
TB = (11.0, 65.0, 18.0, 44.0)        # = make_textures.TOE_BOX
uv = bm.loops.layers.uv.new("proj")
uv_sole = bm.loops.layers.uv.new("sole")
for f in bm.faces:
    cen = f.calc_center_median()
    n = f.normal
    part = seg[f]
    if part == "front":
        idx = I_CARBON
    elif cen.y < FACE_T - SEAM:
        idx = I_LACQ                                 # the face plate is black all round
    elif cen.y < FACE_T + SEAM:
        idx = I_SEAM
    elif part == "lower":
        idx = I_SOLE if n.z < -0.25 else I_BRASS     # sole plate and lower chamfers: brass
    elif cen.y > NOSE_Y:
        idx = I_BRASS                                # back weight: everything behind the boundary plane - side wall /
                                                     # back face, upper chamfer and crown (top-view photo)
    elif part in ("cham", "crown"):
        idx = I_TOP
    elif n.x > 0.3:
        idx = I_HEEL
    elif n.x < -0.3:
        idx = I_TOE
    else:
        idx = I_LACQ
    f.material_index = idx
    f.smooth = True
    for l in f.loops:
        p = l.vert.co
        if idx == I_TOP:
            q = (p.y / HEAD_D, 1 - (p.x + HEAD_W / 2) / HEAD_W)
        elif idx == I_HEEL:
            q = ((p.y - HB[0]) / (HB[1] - HB[0]), (p.z - HB[2]) / (HB[3] - HB[2]))
        elif idx == I_TOE:
            q = ((TB[1] - p.y) / (TB[1] - TB[0]), (p.z - TB[2]) / (TB[3] - TB[2]))
        elif idx == I_CARBON:
            q = (p.x / 4.33, p.z / 4.22)             # weave tile measured on the face photo
        else:
            q = (p.x / 50.0, p.y / 50.0)
        l[uv].uv = q
        l[uv_sole].uv = ((p.x + HEAD_W / 2) / HEAD_W, 1 - p.y / HEAD_D)
_part = np.array([vpart[v] for v in bm.verts])
head = mesh_obj("DP501_Head", bm)
for m in HEAD_MATS:
    head.data.materials.append(m)
# smooth shading from the surface's own normals (not from the triangles): even reflections, crisp creases
_me = head.data
_co = np.zeros(len(_me.vertices) * 3)
_me.vertices.foreach_get("co", _co)
_vn = head_normals(_co.reshape(-1, 3), _part)
_lv = np.zeros(len(_me.loops), dtype=np.int64)
_me.loops.foreach_get("vertex_index", _lv)
_ln = _vn[_lv]
_pn = np.zeros(len(_me.polygons) * 3)
_me.polygons.foreach_get("normal", _pn)
_pn = _pn.reshape(-1, 3)
_ps = np.zeros(len(_me.polygons), dtype=np.int64)
_me.polygons.foreach_get("loop_start", _ps)
_pt = np.zeros(len(_me.polygons), dtype=np.int64)
_me.polygons.foreach_get("loop_total", _pt)
_pc = np.zeros(len(_me.polygons) * 3)
_me.polygons.foreach_get("center", _pc)
_pc = _pc.reshape(-1, 3)
for i in np.nonzero((_pn[:, 1] < -0.99) & (_pc[:, 1] < 0.02))[0]:        # the flat carbon face keeps its own normal
    _ln[_ps[i]:_ps[i] + _pt[i]] = (0.0, -1.0, 0.0)
_me.normals_split_custom_set([tuple(v) for v in _ln])

# ---- brass pins in the face, flush, slightly domed
pins = []
for px, pz in PINS:
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=PIN_R, radius2=PIN_R, depth=2.0,
                          matrix=Matrix.Translation((px, 0.96, pz)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    o = mesh_obj("DP501_FacePin", bm)
    o.data.materials.append(M_PIN)
    pins.append(o)

# ================================================================ shaft, ferrule, grip
D = Vector((math.cos(LIE), 0.0, math.sin(LIE)))
FRONT = Vector((-math.sin(LIE), 0.0, math.cos(LIE)))     # printed side faces the toe (photos: same side as PARKER)
SIDE = D.cross(FRONT)                                      # = -Y: image top of the wrap
TOP_Z = float(S.surfaces(np.array([HOLE[0]]), np.array([HOLE[1]]))["zt"][0])
P_TOP = Vector((HOLE[0], HOLE[1], TOP_Z))
P0 = P_TOP - D * (TOP_Z / D.z)                             # axis meets the sole plane here
S_HEAD = TOP_Z / D.z                                       # axis length from the sole plane to the head top


def axis(s):
    return P0 + D * s


def tube(name, s0, s1, radius_at, steps, mats, uv_fn=None, seg=96, cap_top=False):
    if WEB:
        steps, seg = max(1, round(steps * 0.45)), 64
    bm = bmesh.new()
    lay = bm.loops.layers.uv.new("proj")
    rings = []
    for i in range(steps + 1):
        s = s0 + (s1 - s0) * i / steps
        r = radius_at(s)
        rings.append([bm.verts.new(axis(s) + r * (math.cos(th) * FRONT + math.sin(th) * SIDE))
                      for th in (math.pi + 2 * math.pi * j / seg for j in range(seg))])
    for i in range(steps):
        for j in range(seg):
            k = (j + 1) % seg
            f = bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
            if uv_fn:
                for l, (ii, jj) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                    l[lay].uv = uv_fn(s0 + (s1 - s0) * ii / steps, jj / seg)
    if cap_top:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = mesh_obj(name, bm)
    for m in mats:
        o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def shaft_r(s):
    return SHAFT_R0 + (SHAFT_R1 - SHAFT_R0) * min(1.0, max(0.0, (s - (S_HEAD + 12)) / (CLUB_LEN - GRIP_LEN - S_HEAD - 12)))


m, nt, b = principled("DP501_Shaft")
b.inputs["Base Color"].default_value = BLACK
b.inputs["Roughness"].default_value = 0.1
b.inputs["Coat Weight"].default_value = 1.0
b.inputs["Coat Roughness"].default_value = 0.012
t = tex(nt, img("shaft_wrap.png"))
tm = tex(nt, img("shaft_wrap_metal.png", False))
nt.links.new(mix_rgb(nt, t.outputs["Alpha"], BLACK, t.outputs["Color"]), b.inputs["Base Color"])
nt.links.new(tm.outputs["Color"], b.inputs["Metallic"])                  # per ink: gold / silver metallic, white not
nt.links.new(mix_f(nt, t.outputs["Alpha"], 0.1, 0.22), b.inputs["Roughness"])
M_SHAFT = m
shaft = tube("DP501_Shaft", S_HEAD - 6, CLUB_LEN - GRIP_LEN + 6, shaft_r, 260, [M_SHAFT],
             uv_fn=lambda s, v: ((WRAP[1] - s) / (WRAP[1] - WRAP[0]), v))

# ferrule: sits on the head top (its foot is level, its top square to the shaft), FERRULE_LEN along the axis at the
# centre line, so 12.5 +- 2.5 mm on its long (toe) and short (heel) sides
fa = S_HEAD - 4.0
fb = S_HEAD + FERRULE_LEN
def ferrule_r(s):
    e = fb - s
    return FERRULE_R - (0.9 - math.sqrt(max(0.0, 0.81 - (0.9 - e) ** 2)) if e < 0.9 else 0.0)
M_FER = simple("DP501_Ferrule", BLACK, 0.0, 0.08, 1.0)
ferrule = tube("DP501_Ferrule", fa, fb, ferrule_r, 40, [M_FER])
cap_r = tube("DP501_FerruleTop", fb - 0.02, fb, lambda s: FERRULE_R - 0.9, 1, [M_FER], cap_top=True)
bc = fb - BAND_FROM_TOP
band = tube("DP501_FerruleBand", bc - BAND_H / 2, bc + BAND_H / 2, lambda s: FERRULE_R + 0.03, 3, [holo_band()])

# grip
G0 = CLUB_LEN - GRIP_LEN


def grip_r(s):
    e = CLUB_LEN - s                                        # mm from the grip end
    r = 14.0
    if e < 2.2:                                             # rounded end
        r = 12.2 + math.sqrt(max(0.0, 2.2 ** 2 - (2.2 - e) ** 2)) * (1.8 / 2.2)
    elif e > 0.714 * GRIP_LEN:
        r = 14.0 - 1.4 * ((e - 0.714 * GRIP_LEN) / (0.286 * GRIP_LEN)) ** 1.3
    if e > GRIP_LEN - 3:                                    # lip down onto the shaft
        r = SHAFT_R1 + (r - SHAFT_R1) * max(0.0, (GRIP_LEN - e) / 3) ** 0.5
    return r


m, nt, b = principled("DP501_Grip")
ta = tex(nt, img("grip_albedo.png"), extension="REPEAT")
tb = tex(nt, img("grip_bump.png", False), extension="REPEAT")
nt.links.new(ta.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.62
b.inputs["Specular IOR Level"].default_value = 0.35
bp = node(nt, "ShaderNodeBump", Strength=1.2, Distance=0.0011)
nt.links.new(tb.outputs["Color"], bp.inputs["Height"])
nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
M_GRIP = m
grip = tube("DP501_Grip", G0 - 0.5, CLUB_LEN, grip_r, 360, [M_GRIP],
            uv_fn=lambda s, v: (v, 1 - (CLUB_LEN - s) / GRIP_LEN))
# end cap with the logo (front of the logo toward the printed side)
bm = bmesh.new()
lay = bm.loops.layers.uv.new("proj")
c = axis(CLUB_LEN)
rr = grip_r(CLUB_LEN - 0.01)
vs = [bm.verts.new(c + rr * (math.cos(th) * FRONT + math.sin(th) * SIDE)) for th in
      (2 * math.pi * j / 96 for j in range(96))]
f = bm.faces.new(vs)
for l in f.loops:
    dv = l.vert.co - c
    l[lay].uv = (0.5 + dv.dot(SIDE) / (2 * 14.0), 0.5 + dv.dot(FRONT) / (2 * 14.0))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
cap = mesh_obj("DP501_GripCap", bm)
m, nt, b = principled("DP501_GripCap")
tc = tex(nt, img("grip_cap.png"))
nt.links.new(tc.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.55
cap.data.materials.append(m)


def web_export():
    """Light model for the website's 3D viewer (--web): the same shapes with sparser rows and columns, and the
    render materials rebuilt from plain images (web_textures.py: decals, glitter sole, carbon weave, grip) because
    glTF cannot carry Blender's node mixes; WebP textures in one GLB -> dp501_parkgolf.glb."""
    import tempfile
    import web_textures as WT
    tmp = tempfile.mkdtemp(prefix="dp501_web_")
    # the web viewer maps colours without the render's AgX roll-off, so the same brass reads about 1.7x more
    # saturated there (measured in the viewer, Lab chroma 42 vs 25): the web model takes the colours toward grey
    desat = lambda c, k: tuple([(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) * (1 - k) + v * k for v in c[:3]]) + (1,)
    wbrass = desat(BRASS, 0.62)
    wglit = dict(GLIT, color=desat(GLIT["color"], 0.70))
    p = lambda n: os.path.join(tmp, n)
    top = WT.decal("top_decal.png", p("top"), BLACK)
    heel = WT.decal("side_heel.png", p("heel"), BLACK)
    toe = WT.decal("side_toe.png", p("toe"), BLACK)
    sole_t = WT.sole(p("sole"), wbrass, wglit, BLACK, HEAD_W, HEAD_D)
    carb = WT.carbon(p("carbon"), (0.135, 0.145, 0.19, 1))
    grip_t = WT.grip(p("grip"), GRIP_LEN, math.pi * 28.0)
    shaft_t = WT.shaft(p("shaft"), BLACK)
    cap_t = WT.cap(p("cap"))

    def wmat(name, base=BLACK, rough=0.4, metal=0.0, uv="proj", base_img=None, mr_img=None, n_img=None,
             ext="EXTEND", coat=0.0, coat_rough=0.03):
        m, nt, b = principled(name + "_web")
        b.inputs["Base Color"].default_value = base
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = coat_rough

        def t(path, srgb):
            im = bpy.data.images.load(path)
            im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
            return tex(nt, im, uv, ext)
        if base_img:
            nt.links.new(t(base_img, True).outputs["Color"], b.inputs["Base Color"])
        if mr_img:
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(t(mr_img, False).outputs["Color"], sep.inputs[0])
            nt.links.new(sep.outputs[1], b.inputs["Roughness"])
            nt.links.new(sep.outputs[2], b.inputs["Metallic"])
        if n_img:
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.uv_map = uv
            nt.links.new(t(n_img, False).outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        return m

    gloss = dict(coat=1.0, coat_rough=0.012)
    web = {
        "DP501_Lacquer": wmat("DP501_Lacquer", BLACK, 0.12, **gloss),
        "DP501_TopGraphic": wmat("DP501_TopGraphic", base_img=top[0], mr_img=top[1], **gloss),
        "DP501_HeelLettering": wmat("DP501_HeelLettering", base_img=heel[0], mr_img=heel[1], **gloss),
        "DP501_ToeLettering": wmat("DP501_ToeLettering", base_img=toe[0], mr_img=toe[1], **gloss),
        "DP501_CarbonFace": wmat("DP501_CarbonFace", base_img=carb[0], mr_img=carb[1], n_img=carb[2], ext="REPEAT",
                                 coat=1.0, coat_rough=0.045),
        "DP501_Brass": wmat("DP501_Brass", wbrass, 0.27, 1.0),
        "DP501_SoleEngraved": wmat("DP501_SoleEngraved", uv="sole", base_img=sole_t[0], mr_img=sole_t[1],
                                   n_img=sole_t[2]),
        "DP501_FacePin": wmat("DP501_FacePin", wbrass, 0.37, 1.0),
        "DP501_FacePlateSeam": wmat("DP501_FacePlateSeam", (0.002, 0.002, 0.002, 1), 0.55),
        "DP501_Shaft": wmat("DP501_Shaft", base_img=shaft_t[0], mr_img=shaft_t[1], **gloss),
        "DP501_Ferrule": wmat("DP501_Ferrule", BLACK, 0.08, coat=1.0, coat_rough=0.015),
        "DP501_HoloBand": wmat("DP501_HoloBand", (0.80, 0.56, 0.20, 1), 0.2, 1.0),
        "DP501_Grip": wmat("DP501_Grip", rough=0.62, base_img=grip_t[0], n_img=grip_t[1], ext="REPEAT"),
        "DP501_GripCap": wmat("DP501_GripCap", rough=0.55, base_img=cap_t),
    }
    tris = 0
    for o in col.objects:
        if o.type == "MESH":
            for slot in o.material_slots:
                slot.material = web[slot.material.name.replace("_web", "")]
            tris += sum(len(f.vertices) - 2 for f in o.data.polygons)
    out = os.path.join(HERE, "dp501_parkgolf.glb")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=False, export_apply=True,
                              export_yup=True, export_image_format="WEBP", export_image_quality=88,
                              export_cameras=False, export_lights=False)
    print("web model %s: %d triangles, %d KB" % (out, tris, os.path.getsize(out) // 1024))


# ================================================================ assembly + exports
root = link(bpy.data.objects.new("GRAZR_DP501", None))
for o in list(col.objects):
    if o is not root and o.type == "MESH":
        o.parent = root
        o.data.name = o.name
root.scale = (0.001, 0.001, 0.001)
bpy.context.view_layer.update()
print("axis meets the sole at X=%.1f (heel end 53 -> %.1f mm), club length %.0f" % (P0.x, 53 - P0.x, CLUB_LEN))
if WEB:
    web_export()
    sys.exit(0)
bpy.ops.file.pack_all()
if not (os.environ.get("BRASS") or os.environ.get("GLIT")):   # a calibration build is not the model: keep the file
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "dp501_parkgolf.blend"))
if not RENDER:
    sys.exit(0)

# ================================================================ renders
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
world = bpy.data.worlds.new("studio")
world.use_nodes = True
# (height of the direction z = -1 .. 1, brightness): a bright floor well below the horizon (the brass sole and the lower
# curves face it), a dark band round the horizon (keeps the lacquer walls black), a dim overhead
WORLD_STOPS = [(-1.0, 0.50), (-0.62, 0.50), (-0.30, 0.04), (0.10, 0.04), (1.0, 0.14)]
if os.environ.get("WORLD_STOPS"):
    WORLD_STOPS = [tuple(map(float, t.split(":"))) for t in os.environ["WORLD_STOPS"].split(",")]


def studio_world(stops=WORLD_STOPS):
    """Soft studio dome, seen only in reflections (the background is composited)."""
    nt = world.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    mr = node(nt, "ShaderNodeMapRange", **{"From Min": -1.0, "From Max": 1.0})
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (z, v) in zip(els, stops):
        e.position = (z + 1) / 2
        e.color = (v, v, v * 1.03, 1)
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    return ramp


def world_floor(v):
    """Brightness of the dome's floor (the two lowest stops)."""
    for e in sorted(WORLD_RAMP.color_ramp.elements, key=lambda e: e.position)[:2]:
        e.color = (v, v, v * 1.03, 1)


WORLD_RAMP = studio_world()
scene.world = world
cam_data = bpy.data.cameras.new("cam")
cam_data.clip_start = 0.001
cam = link(bpy.data.objects.new("Camera", cam_data))
scene.camera = cam
CLUB = (shaft, grip, cap)


def area(name, loc, target, size, power, color=(1, 1, 1), glossy=True):
    """glossy=False: the light shows in no reflection (a diffuse-only fill for printed / lacquered parts)."""
    li = bpy.data.lights.new(name, "AREA")
    if isinstance(size, tuple):
        li.shape = "RECTANGLE"
        li.size, li.size_y = size
    else:
        li.size = size
    li.energy = power
    li.color = color
    ob = link(bpy.data.objects.new(name, li))
    ob.visible_glossy = glossy
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def look(loc, target, up=(0, 0, 1)):
    f = (Vector(target) - Vector(loc)).normalized()
    up = Vector(up)
    if abs(f.dot(up.normalized())) > 0.999:
        up = Vector((0, 1, 0))
    r = f.cross(up).normalized()
    return Matrix((r, r.cross(f), -f)).transposed().to_euler()


def shot(name, loc, target, lens, lights, up=(0, 0, 1), head_only=False, res=(1600, 1200), folder="renders",
         ortho=None, bg=0.93, shift=(0.0, 0.0), glow=(0.5, 0.42)):
    """shift: lens shift (fractions of the larger image side; +x moves the picture left). glow: centre of the
    faint backdrop glow in dark shots (fractions of width / height from the top left)."""
    only = os.environ.get("ONLY")
    if only and name not in only.split(","):
        return
    for o in CLUB:
        o.hide_render = head_only
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    cam.rotation_euler = look(loc, target, up)
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = "PERSP"
        cam_data.lens = lens
    cam_data.shift_x, cam_data.shift_y = shift
    for o in [o for o in col.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    for li in lights:
        area(*li)
    os.makedirs(os.path.join(HERE, folder), exist_ok=True)
    path = os.path.join(HERE, folder, name + ".png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path)
    px = np.array(im.pixels[:]).reshape(-1, 4)
    a = px[:, 3:4]
    back = np.full((len(px), 1), bg)
    if bg < 0.5:                              # dark studio: a faint glow behind the club, black towards the edges
        W, H = res
        k = np.arange(len(px))
        gx, gy = (k % W) / W - glow[0], (k // W) / H - glow[1]
        back += 0.035 * np.clip(1.0 - (gx * gx + gy * gy) / 0.22, 0, None)[:, None]
    px[:, :3] = px[:, :3] * a + back * (1 - a)
    px[:, 3] = 1.0
    im.pixels = px.ravel()
    im.save()
    bpy.data.images.remove(im)
    print("  ->", path, flush=True)


mm = lambda *v: Vector(v) * 0.001
HC = mm(0, 46, 28)


def studio(c=HC, d=1.0):
    return [("key", c + Vector((-0.36, -0.30, 0.44)) * d, c, (0.9 * d, 0.6 * d), 7.0 * d * d),
            ("top", c + Vector((0.0, 0.12, 0.62)) * d, c, (1.4 * d, 1.0 * d), 5.0 * d * d),
            ("rimL", c + Vector((-0.42, 0.42, 0.22)) * d, c, (0.12 * d, 0.9 * d), 4.0 * d * d),
            ("rimR", c + Vector((0.44, 0.40, 0.24)) * d, c, (0.12 * d, 0.9 * d), 4.0 * d * d),
            ("fill", c + Vector((0.46, -0.22, 0.12)) * d, c, (0.8 * d, 0.8 * d), 1.4 * d * d),
            ("low", c + Vector((-0.10, -0.30, -0.36)) * d, c, (0.9 * d, 0.6 * d), 1.2 * d * d, (1.0, 0.92, 0.8))]


below = lambda L_: [(l[0], Vector((l[1].x, l[1].y, 2 * HC.z - l[1].z))) + tuple(l[2:]) for l in L_]
dim = lambda L_, k: [(l[0], l[1], l[2], l[3], l[4] * k) + tuple(l[5:]) for l in L_]   # the sole photos: a darker room

if ORTHO:
    flat = [("a", HC + Vector((0, 0, 0.6)), HC, 1.2, 25.0), ("b", HC + Vector((0, -0.6, 0.1)), HC, 1.2, 12.0),
            ("c", HC + Vector((0.6, 0, 0.1)), HC, 1.2, 12.0), ("d", HC + Vector((-0.6, 0, 0.1)), HC, 1.2, 12.0),
            ("e", HC + Vector((0, 0.6, 0.1)), HC, 1.2, 12.0), ("f", HC + Vector((0, 0, -0.6)), HC, 1.2, 12.0)]
    o = dict(folder="check", head_only=True, ortho=0.13, res=(1300, 1300))
    shot("top", HC + mm(0, 0, 400), HC, 0, flat, up=(-1, 0, 0), **o)
    shot("heel", HC + mm(400, 0, 0), HC, 0, flat, **o)
    shot("toe", HC + mm(-400, 0, 0), HC, 0, flat, **o)
    shot("bottom", HC + mm(0, 0, -400), HC, 0, flat, up=(0, -1, 0), **o)
    shot("front", HC + mm(0, -400, 0), HC, 0, flat, **o)
    shot("back", HC + mm(0, 400, 0), HC, 0, flat, **o)
    sys.exit(0)

if MATCH:
    # cameras solved from the photos' silhouettes (pinhole, f and principal point in px of the W x H photo)
    import json
    cams = json.load(open(os.path.join(HERE, "check", "photo_cams.json")))
    for name, c in cams.items():
        only = os.environ.get("ONLY")
        if only and name not in only.split(","):
            continue
        rot = Matrix((Vector(c["rt"]), Vector(c["up"]), -Vector(c["fw"]))).transposed()
        cam.location = Vector(c["C"]) * 0.001
        cam.rotation_euler = rot.to_euler()
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "HORIZONTAL"
        cam_data.sensor_width = 36.0
        cam_data.lens = c["f"] * 36.0 / c["W"]
        cam_data.shift_x = -(c["cx"] - c["W"] / 2) / c["W"]
        cam_data.shift_y = (c["cy"] - c["H"] / 2) / c["W"]
        sole = c["fw"][2] > 0.5
        world_floor(0.12)                # the photos were taken over a dark table / room, not a bright floor
        lights = dim(below(studio()), 0.6) if sole else studio()
        for o in CLUB:
            o.hide_render = False
        k = float(os.environ.get("MATCH_RES", "1400")) / max(c["W"], c["H"])
        scene.render.resolution_x, scene.render.resolution_y = round(c["W"] * k), round(c["H"] * k)
        for o in [o for o in col.objects if o.type == "LIGHT"]:
            bpy.data.objects.remove(o, do_unlink=True)
        for li in lights:
            area(*li)
        path = os.path.join(os.environ.get("MATCH_DIR", os.path.join(HERE, "check")), "match_%s.png" % name)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("  ->", path, flush=True)
    world_floor(WORLD_STOPS[0][1])
    print("done")
    sys.exit(0)

if PHOTO:
    o = dict(folder="check", res=(1400, 1400), bg=1.0)
    shot("photo_face", HC + mm(0, -1100, 50), HC + mm(0, 0, 0), 200, studio() + [
        ("sheen", HC + Vector((-0.10, -0.40, 0.30)), HC, 0.8, 1.2)], **o)
    world_floor(0.12)
    shot("photo_sole", HC + mm(0, 0, -1100), HC, 200, dim(below(studio()), 0.6), up=(0, -1, 0), head_only=True, **o)
    world_floor(WORLD_STOPS[0][1])
    shot("photo_back", HC + mm(20, 1100, 75), HC + mm(0, 0, 4), 200, studio(), **o)
    # from above, looking down along the shaft as the owner's top-view photo (face left, nose right, toe up)
    shot("photo_top", HC + mm(62, 6, 470), HC + mm(6, 2, 36), 62, studio(), up=(-1, 0, 0), **o)
    mid = axis(400) * 0.001
    u = Vector((0, -1, 0)) * math.cos(math.radians(28)) + Vector(FRONT) * math.sin(math.radians(28))
    shot("photo_full", mid + u * 2.6, mid, 85,
         [("key", mid + Vector((-0.8, -1.5, 1.2)), mid, 1.0, 70), ("fill", mid + Vector((1.2, -0.7, 0.4)), mid, 1.5, 30),
          ("rim", mid + Vector((0.3, 1.3, 0.9)), mid, 1.0, 60)], up=tuple(D), res=(800, 1600), folder="check", bg=1.0)
    print("done")
    sys.exit(0)

if SITE:
    dark = dict(bg=0.0, folder="site")
    key = lambda c, d=0.7: [
        ("key", c + Vector((-0.35, -0.30, 0.40)) * d, c, 0.35 * d, 9.0),
        ("rim", c + Vector((0.30, 0.55, 0.30)) * d, c, 0.25 * d, 10.0),
        ("rim2", c + Vector((-0.45, 0.45, 0.20)) * d, c, 0.25 * d, 6.0),
        ("strip", c + Vector((0.55, -0.20, 0.25)) * d, c, 0.12 * d, 3.5),
        ("low", c + Vector((-0.10, -0.30, -0.36)) * d, c, 0.6 * d, 1.5, (1.0, 0.92, 0.8)),
    ]
    # hero: whole head right of centre and above the middle (the page copy sits bottom left over the dark)
    d_h = Vector((-0.30, -0.24, 0.13)).normalized()
    shot("hero", HC + d_h * 0.70, HC + mm(0, 0, 4), 70, key(HC),
         res=(1920, 1080), shift=(-0.10, -0.094), glow=(0.60, 0.33), **dark)
    # phones crop the 4:5 picture to its middle: head centred, upper half, copy below
    d_m = Vector((-0.22, -0.30, 0.16)).normalized()
    shot("hero_m", HC + d_m * 0.60, HC + mm(0, 0, 4), 60, key(HC),
         res=(1080, 1350), shift=(0.045, -0.13), glow=(0.5, 0.33), **dark)
    mid = axis(430) * 0.001
    full_l = [("key", mid + Vector((-0.8, -1.5, 1.2)), mid, 1.0, 70), ("rim", mid + Vector((0.6, 1.2, 0.8)), mid, 0.8, 60),
              ("rim2", mid + Vector((-1.0, 0.8, 0.3)), mid, 0.8, 35)]
    shot("full", mid + Vector((-0.7, -2.2, 0.35)), mid, 85, full_l, res=(1200, 1500), **dark)
    shot("card", HC + Vector((-0.26, -0.28, 0.30)), HC + Vector((0.01, 0.0, 0.05)), 50, key(HC), res=(1200, 1500),
         **dark)
    back_c = mm(0, 84, 26)
    # brass weight from behind the heel: soft lights so the glossy crown does not flare, shaft kept
    soft = [("key", back_c + Vector((-0.20, 0.10, 0.32)), back_c, 0.45, 7.0),
            ("fill", back_c + Vector((0.32, 0.12, 0.04)), back_c, 0.35, 3.0),
            ("rim", back_c + Vector((0.05, -0.30, 0.22)), back_c, 0.25, 5.0),
            ("low", back_c + Vector((-0.05, 0.25, -0.25)), back_c, 0.5, 1.2, (1.0, 0.92, 0.8))]
    shot("f_brass", back_c + Vector((0.12, 0.36, 0.11)), back_c + mm(0, -10, 0), 85, soft, res=(1280, 960),
         shift=(-0.08, 0.06), glow=(0.5, 0.5), **dark)
    shot("f_maple", HC + Vector((0.40, -0.10, 0.06)), HC, 85, key(HC), res=(1280, 960), **dark)
    sc = axis(PRINT_MID) * 0.001
    # like the film's shaft shot: a diffuse-only fill for the print (a softbox in the lacquer would lay a grey band
    # over it) and two thin strips behind the shaft for the crisp edge lines of the photos
    cam_l = sc + Vector(FRONT) * 0.30 + mm(0, -40, 0)
    cd = (cam_l - sc).normalized()
    shaft_l = [("fill", sc + Vector(FRONT) * 0.35 + Vector((0, -0.25, 0.20)), sc, (0.5, 0.8), 7.0, (1, 1, 1), False)]
    for nm, ang, pw in (("stripL", 112.0, 4.5), ("stripR", -108.0, 3.8)):
        shaft_l.append((nm, sc + (Matrix.Rotation(math.radians(ang), 3, Vector(D)) @ cd) * 0.30, sc, (0.03, 0.9), pw))
    shot("f_shaft", cam_l, sc, 85, shaft_l, up=tuple(D), res=(1280, 960),
         **dark)
    shot("f_aim", HC + Vector((0.10, 0.05, 0.38)), HC, 70, key(HC), up=(-1, 0, 0), res=(1280, 960), **dark)
    # 3D viewer poster = the viewer's first view (website dp501.html: camera-target 0m 0.038m -0.046m,
    # camera-orbit -40deg 68deg 0.44m, field-of-view 25deg vertical), so nothing jumps when the model loads
    th, ph = math.radians(-40.0), math.radians(68.0)
    pv = Vector((math.sin(ph) * math.sin(th), -math.sin(ph) * math.cos(th), math.cos(ph)))   # glTF -> Blender
    shot("poster", HC + mm(0, 0, 10) + pv * 0.44, HC + mm(0, 0, 10), 20.25 / 2 / math.tan(math.radians(12.5)),
         key(HC), res=(1280, 720), glow=(0.5, 0.5), **dark)
    print("done")
    sys.exit(0)

shot("01_hero", HC + mm(-300, -340, 230), HC + mm(4, 0, 10), 85, studio())
# face: an extra broad soft box above the camera lays a sheen over the upper face, as in the face photo
shot("02_face", HC + mm(0, -430, 25), HC + mm(0, 0, 4), 100,
     studio() + [("sheen", HC + Vector((-0.10, -0.40, 0.30)), HC, 0.8, float(os.environ.get("SHEEN", "1.2")))])
shot("03_top", HC + mm(0, 0, 460), HC, 85, studio(), up=(-1, 0, 0), head_only=True)
shot("04_back", HC + mm(80, 470, 120), HC + mm(0, 0, 8), 85, studio())
world_floor(float(os.environ.get("SOLE_FLOOR", "0.12")))   # seen from below the sole faces the floor: keep it dim,
shot("05_sole", HC + mm(0, 0, -460), HC, 85, dim(below(studio()), 0.6), up=(0, -1, 0), head_only=True)   # as in the sole photo
world_floor(WORLD_STOPS[0][1])
shot("06_toe", HC + mm(-440, 0, 40), HC, 90, studio(), head_only=True)
shot("07_heel", HC + mm(440, 0, 40), HC, 90, studio(), head_only=True)
mid = axis(430) * 0.001
shot("08_full", mid + Vector((-0.75, -2.3, 0.2)), mid, 85,
     [("key", mid + Vector((-0.9, -1.4, 1.2)), mid, 1.2, 90), ("fill", mid + Vector((1.2, -0.7, 0.4)), mid, 1.5, 30),
      ("rim", mid + Vector((0.3, 1.3, 0.9)), mid, 1.0, 60)], res=(1200, 1600))
sc = axis(PRINT_MID) * 0.001
toe_view = Vector(FRONT) * 0.36
# strip lights to the sides: thin crisp highlights along the shaft's edges (as in the photos), print left readable
shot("09_shaft", sc + toe_view + mm(0, -40, 0), sc, 85,
     [("key", sc + Vector(FRONT) * 0.22 + Vector((0, -0.30, 0.10)), sc, (0.06, 0.6), 6.0),
      ("fill", sc + Vector(FRONT) * 0.22 + Vector((0, 0.32, 0.0)), sc, (0.05, 0.6), 3.0),
      ("soft", sc + Vector(FRONT) * 0.45 + Vector((0, 0.0, 0.45)), sc, 0.8, 3.0)],
     up=tuple(D), res=(1200, 1600))
gc = axis(CLUB_LEN - 160) * 0.001                  # whole grip from the cap (star, round logo) to the GRAZR label
shot("10_grip", gc + Vector(FRONT) * 0.74 + mm(0, -90, 0), gc, 85,
     [("key", gc + Vector(FRONT) * 0.5 + Vector((0, -0.35, 0.25)), gc, 0.6, 12.0),
      ("fill", gc + Vector(FRONT) * 0.4 + Vector((0, 0.4, -0.05)), gc, 0.7, 5.0)],
     up=tuple(D), res=(900, 1800))
print("done")
