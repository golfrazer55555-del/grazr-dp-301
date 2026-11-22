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
from scipy.interpolate import PchipInterpolator
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
RENDER = "--no-render" not in sys.argv
ORTHO = "--ortho" in sys.argv
SAMPLES = int(os.environ.get("SAMPLES", "128"))

# ================================================================ measured shape (SPEC.md)
HEAD_W, HEAD_D, HEAD_H = 106.0, 95.0, 56.0
FACE_T = 8.0
NOSE_Y = 81.0
BRASS_Z0, BRASS_Z1 = 17.5, 19.5          # brass / lacquer line on the sides at Y = FACE_T and Y = NOSE_Y
K_Y = 95.0 / 94.4                        # side drawing length -> top drawing length

# top-view outline: the measured points of the top and bottom drawings fit a superellipse behind Y = 26
# (rms 0.13 mm, max 0.4 mm), so the smooth curve is used instead of the noisy points
SE_Y0, SE_N, SE_M = 26.19, 1.592, 1.6
CORNER_R = 1.0                                # small vertical round on the face plate corners
K_Y = 95.0 / 94.4                            # side drawing length -> top drawing length


def _se_xy(th):
    return 53.0 * np.cos(th) ** (2 / SE_N), SE_Y0 + (HEAD_D - SE_Y0) * np.sin(th) ** (2 / SE_M)


def _tip_arc(R=7.0):
    """Round the superellipse's point with a circle of radius R tangent to it (the drawing's nose is rounded)."""
    th = np.linspace(0.05, np.pi / 2 - 1e-4, 20000)
    x, y = _se_xy(th)
    dx, dy = np.gradient(x, th), np.gradient(y, th)
    nx, ny = -dy, dx                                         # inward normal (towards the centre line)
    nn = np.hypot(nx, ny)
    nx, ny = nx / nn, ny / nn
    t = -x / nx                                              # normal line meets the centre line X = 0
    yc = y + t * ny
    i = int(np.argmin(np.abs(t - R)))
    return float(th[i]), float(y[i]), float(yc[i]), float(t[i])


TH_T, Y_T, Y_C, TIP_R = _tip_arc()
TIP_Y = Y_C + TIP_R                                          # back end of the head (about 95)


def half_width(y):
    y = np.asarray(y, float)
    t = np.clip((y - SE_Y0) / (HEAD_D - SE_Y0), 0, 1)
    w = 53.0 * np.clip(1 - t ** SE_M, 0, 1) ** (1 / SE_N)
    arc = np.sqrt(np.clip(TIP_R ** 2 - (y - Y_C) ** 2, 0, None))
    w = np.where(y > Y_T, arc, w)
    corner = 53.0 - CORNER_R + np.sqrt(np.clip(CORNER_R ** 2 - (CORNER_R - y) ** 2, 0, None))
    return np.where(y < CORNER_R, corner, w)


def _top_line(y):
    """Side drawing top silhouette: flat to Y 46, then 56 - 0.0082 (Y-46)^1.8 (rms 0.21 mm to the drawing);
    the last 1.5 mm rounds down into the nose tip at 43.6."""
    y = np.asarray(y, float)
    z = 56.0 - 0.00819673 * np.clip(y - 46.0, 0, None) ** 1.79798
    z95 = 56.0 - 0.00819673 * (95.0 - 46.0) ** 1.79798
    return z - (z95 - 43.6) * np.clip((y - 93.5) / 1.5, 0, 1) ** 2.2


def _bot_line(y):
    """Side drawing bottom silhouette: flat, then a straight 22 deg rise (z = 0.4037 Y - 17.41, residual < 0.15 mm)
    with a soft start, then the nose end rising into the tip (measured points)."""
    y = np.asarray(y, float)
    k = 0.6
    return k * np.log1p(np.exp((0.40372 * y - 17.4084) / k))


_ys = np.arange(0.0, 93.51, 0.5)
_st = PchipInterpolator(_ys.tolist() + [94.0, 94.5, 95.0], _top_line(np.concatenate([_ys, [94.0, 94.5, 95.0]])))
_yb = np.arange(0.0, 87.51, 0.5)
_sb = PchipInterpolator(_yb.tolist() + [89.9, 92.0, 94.0, 95.0],
                        np.concatenate([_bot_line(_yb), [21.4, 30.4, 39.8, 43.6]]))
# front cross-section half profile (x, z): top round, outward-leaning wall, lower curve, flat sole
TOP_PROFILE = [(0, 56.0), (25.0, 56.0), (27.0, 55.92), (31.0, 55.4), (35.0, 54.5), (38.5, 53.3), (41.5, 51.9),
               (44.2, 50.2), (46.6, 48.4), (48.8, 46.5), (50.6, 44.6), (51.9, 42.8), (52.7, 41.3), (53.0, 40.0)]
BOT_PROFILE = [(0, 0.0), (20.0, 0.0), (22.5, 0.15), (25.0, 0.6), (27.5, 1.3), (30.0, 2.1), (32.5, 3.0),
               (35.0, 4.1), (37.5, 5.3), (40.0, 6.7), (42.5, 8.2), (44.5, 9.6), (46.3, 11.0), (47.7, 12.4),
               (48.6, 13.6), (49.0, 14.5), (49.6, 16.5), (50.4, 20.0), (51.2, 24.0), (51.8, 28.0), (52.4, 32.0),
               (52.8, 36.0), (53.0, 40.0)]
EDGE_Z = 40.0
PINS = [(-21.0, 48.6), (21.0, 48.6), (-29.4, 14.3), (29.4, 14.3)]
PIN_R = 3.15

# shaft / ferrule / grip
HOLE = (12.9, 30.1)                      # where the shaft axis leaves the head top
LIE = math.radians(75.0)
CLUB_LEN = 850.0
GRIP_LEN = 350.0
FERRULE_R, FERRULE_H = 9.2, 11.0         # visible height, measured vertically at the side
BAND_C, BAND_H = 6.5, 2.1                # holographic band centre / height above the head top (vertical)
SHAFT_R0, SHAFT_R1 = 8.0, 9.75           # at the ferrule / under the grip
WRAP = (200.0, 450.0)                    # shaft graphic band, distance along the axis from the sole plane


def pchip(tab):
    xs, ys = zip(*tab)
    f = PchipInterpolator(np.array(xs, float), np.array(ys, float), extrapolate=True)
    return lambda x: f(np.clip(x, xs[0], xs[-1]))


FRONT_R = 1.0                                 # small round on the face plate's top / bottom front edges


def _front_round(y):
    y = np.asarray(y, float)
    return np.where(y < FRONT_R, FRONT_R - np.sqrt(np.clip(FRONT_R ** 2 - (FRONT_R - y) ** 2, 0, None)), 0.0)


s_top = lambda y: _st(np.clip(np.asarray(y, float) * 95.0 / TIP_Y, 0, 95.0)) - _front_round(y)
s_bot = lambda y: _sb(np.clip(np.asarray(y, float) * 95.0 / TIP_Y, 0, 95.0)) + _front_round(y)
_top = pchip(TOP_PROFILE)
_bot = pchip(BOT_PROFILE)
# The profile points are joined by PCHIP, which is only C1: its curvature jumps at every point and that shows
# as wavy edges in the lacquer reflections. Both curves leave the outline vertically (height ~ sqrt(d)), so they
# are smoothed in r = sqrt(d) with an odd extension through r = 0: U(0) = L(0) = 0 and the top and the wall still
# meet tangentially at the outline, while the curvature is evened out (about 0.3 mm near the edge, 1.5 mm inside).
from scipy.ndimage import gaussian_filter1d  # noqa: E402
_RR = np.arange(-7.5, 7.5001, 0.002)
_rd = np.clip(_RR ** 2, 0, 53.0)
_U_tab = gaussian_filter1d(np.sign(_RR) * (_top(53.0 - _rd) - EDGE_Z), 75.0, mode="nearest")
_L_tab = gaussian_filter1d(np.sign(_RR) * (EDGE_Z - _bot(53.0 - _rd)), 75.0, mode="nearest")
U = lambda d: np.interp(np.sqrt(np.clip(d, 0, 53.0)), _RR, _U_tab)   # height of the top above the edge line
L = lambda d: np.interp(np.sqrt(np.clip(d, 0, 53.0)), _RR, _L_tab)   # depth of the bottom below the edge line

# outline (toe side -> tip -> heel side, the face edge left out), sampled densely
_th = np.linspace(0, TH_T, 6000)
_w, _y = _se_xy(_th)
_ph = np.linspace(np.arctan2(Y_T - Y_C, float(half_width(Y_T))), np.pi / 2, 1500)
_w = np.concatenate([_w, TIP_R * np.cos(_ph)])
_y = np.concatenate([_y, Y_C + TIP_R * np.sin(_ph)])
_yc = np.linspace(0, SE_Y0, 2000)
heel = np.concatenate([np.stack([half_width(_yc), _yc], 1), np.stack([_w, _y], 1)])
outline = np.concatenate([heel * [-1, 1], heel[::-1][1:]])
TREE = cKDTree(outline)

# signed distance on a 0.1 mm grid, mirrored at the face plane, blurred (sigma 2 mm): the rounds keep their
# exact size near the outline, while the crease the plain distance has along the centre line at the back is
# smoothed out (otherwise it shows as a kinked ridge and lumpy reflections)
GX = np.arange(-58.0, 58.0001, 0.1)
GY = np.arange(-6.0, 100.0001, 0.1)
_XX, _YY = np.meshgrid(GX, GY, indexing="ij")
_ay = np.abs(_YY)
_d = TREE.query(np.stack([_XX.ravel(), _ay.ravel()], 1))[0].reshape(_XX.shape)
_inside = (np.abs(_XX) <= half_width(np.minimum(_ay, TIP_Y))) & (_ay <= TIP_Y)
from scipy.ndimage import gaussian_filter, map_coordinates, spline_filter  # noqa: E402
SDF = spline_filter(gaussian_filter(np.where(_inside, _d, -_d), sigma=25.0), order=3)   # cubic: smooth normals


def dist(x, y):
    """Exact distance to the outline near it (keeps the rounds and the nose tip true); the blurred field only
    takes over deeper inside (from 3 to 8 mm), where it smooths the centre-line crease."""
    x = np.ravel(np.asarray(x, float))
    y = np.ravel(np.asarray(y, float))
    dt = TREE.query(np.stack([x, np.abs(y)], 1))[0]
    db = map_coordinates(SDF, [(x - GX[0]) / 0.1, (y - GY[0]) / 0.1], order=3, mode="nearest", prefilter=False)
    w = np.clip((dt - 3.0) / 5.0, 0, 1)
    w = w * w * (3 - 2 * w)
    return dt * (1 - w) + np.minimum(db, dt) * w


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
    return m


BRASS = (0.86, 0.60, 0.19, 1)


def brass(name, engraved=False):
    """Brushed brass, grain along X (toe-heel). Engraved: sand-blasted logos (recessed, sparkly), black DP-501,
    screw outlines; textures on UV 'sole' (planar from below)."""
    m, nt, b = principled(name)
    b.inputs["Base Color"].default_value = BRASS
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.2
    b.inputs["Anisotropic"].default_value = 0.65
    nt.links.new(world_vec(nt, (1, 0, 0)), b.inputs["Tangent"])
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.002, 3.0, 3.0)          # object space is mm: fine hairlines along X
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    nz = node(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=12.0, Roughness=0.7)
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    hair = node(nt, "ShaderNodeBump", Strength=0.08, Distance=0.00002)
    nt.links.new(nz.outputs["Fac"], hair.inputs["Height"])
    normal = hair.outputs["Normal"]
    rough = node(nt, "ShaderNodeMapRange", **{"From Min": 0.3, "From Max": 0.7, "To Min": 0.17, "To Max": 0.25})
    nt.links.new(nz.outputs["Fac"], rough.inputs["Value"])
    rough = rough.outputs["Result"]
    color = BRASS
    metal = None
    aniso = None
    if engraved:
        e = tex(nt, img("sole_engrave.png", False), "sole")
        k = tex(nt, img("sole_black.png", False), "sole")
        r_ = tex(nt, img("sole_rings.png", False), "sole")
        spark = node(nt, "ShaderNodeTexVoronoi", Scale=9.0)               # sand-blast grains (object mm)
        spark.feature = "F1"
        nt.links.new(coord.outputs["Object"], spark.inputs["Vector"])
        color = mix_rgb(nt, e.outputs["Color"], BRASS, (0.95, 0.76, 0.30, 1))
        color = mix_rgb(nt, r_.outputs["Color"], color, (0.18, 0.12, 0.05, 1))
        color = mix_rgb(nt, k.outputs["Color"], color, (0.012, 0.012, 0.012, 1))
        sr = node(nt, "ShaderNodeMapRange", **{"To Min": 0.38, "To Max": 0.62})
        nt.links.new(spark.outputs["Distance"], sr.inputs["Value"])
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
        gb = node(nt, "ShaderNodeBump", Strength=0.25, Distance=0.00003)
        gm = nt.nodes.new("ShaderNodeMath")
        gm.operation = "MULTIPLY"
        nt.links.new(spark.outputs["Distance"], gm.inputs[0])
        nt.links.new(e.outputs["Color"], gm.inputs[1])
        nt.links.new(gm.outputs[0], gb.inputs["Height"])
        nt.links.new(eb.outputs["Normal"], gb.inputs["Normal"])
        normal = gb.outputs["Normal"]
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
    return m


def carbon_mat():
    """Plain-weave carbon under clear coat: anisotropic per tow (warp along X, weft along Z), tile 4.2 mm."""
    m, nt, b = principled("DP501_CarbonFace")
    t = tex(nt, img("carbon.png", False), "proj", "REPEAT")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t.outputs["Color"], sep.inputs[0])
    warp, height, streak = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    base_dark = (0.010, 0.010, 0.011, 1)
    base_light = (0.045, 0.045, 0.048, 1)
    hs = nt.nodes.new("ShaderNodeMath")
    hs.operation = "MULTIPLY"
    nt.links.new(height, hs.inputs[0])
    sk = node(nt, "ShaderNodeMapRange", **{"To Min": 0.75, "To Max": 1.0})
    nt.links.new(streak, sk.inputs["Value"])
    nt.links.new(sk.outputs["Result"], hs.inputs[1])
    nt.links.new(mix_rgb(nt, hs.outputs[0], base_dark, base_light), b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 0.55
    b.inputs["Roughness"].default_value = 0.3
    b.inputs["Anisotropic"].default_value = 0.9
    tan = nt.nodes.new("ShaderNodeMix")
    tan.data_type = "VECTOR"
    nt.links.new(warp, tan.inputs["Factor"])
    nt.links.new(world_vec(nt, (0, 0, 1)), tan.inputs[4])
    nt.links.new(world_vec(nt, (1, 0, 0)), tan.inputs[5])
    nt.links.new(tan.outputs[1], b.inputs["Tangent"])
    bp = node(nt, "ShaderNodeBump", Strength=0.35, Distance=0.00015)
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
M_PIN = simple("DP501_FacePin", (0.88, 0.64, 0.24, 1), 1.0, 0.3)
M_SEAM = simple("DP501_FacePlateSeam", (0.002, 0.002, 0.002, 1), 0.0, 0.55)
HEAD_MATS = [M_LACQ, M_TOP, M_HEEL, M_TOE, M_CARBON, M_BRASS, M_SOLE, M_SEAM]
I_LACQ, I_TOP, I_HEEL, I_TOE, I_CARBON, I_BRASS, I_SOLE, I_SEAM = range(8)
SEAM = 0.16                                   # glue line between the carbon face plate and the maple body

# ================================================================ head surface
rows = np.concatenate([[0.0, 0.04, 0.1, 0.18, 0.3, 0.45, 0.65, 0.9, 1.25, 1.75, 2.5], np.arange(3.1, 90.0, 0.4),
                       np.arange(90.0, TIP_Y - 0.3, 0.25), [TIP_Y - 0.22, TIP_Y - 0.12, TIP_Y - 0.05]])
rows = np.unique(np.concatenate([rows, [FACE_T, NOSE_Y, 41.3 * K_Y, 42.7 * K_Y]]))
N = 181
cheb = -np.cos(np.pi * np.arange(N) / (N - 1))                  # -1 .. 1, dense near both edges
bm = bmesh.new()
top_rows, bot_rows = [], []
for y in rows:
    w = float(half_width(y))
    xs = cheb * w
    d = dist(xs, np.full(N, y))
    d[0] = d[-1] = 0.0
    dm = float(dist(np.array([0.0]), np.array([y]))[0])
    st, sb = float(s_top(y)), float(s_bot(y))
    u_m, l_m = float(U(dm)), float(L(dm))
    s = (st - sb) / max(u_m + l_m, 1e-6)
    c = st - u_m * s
    zt = c + U(d) * s
    zb = c - L(d) * s
    tr = [bm.verts.new((float(x), float(y), float(z))) for x, z in zip(xs, zt)]
    br = [tr[0]] + [bm.verts.new((float(x), float(y), float(z))) for x, z in zip(xs[1:-1], zb[1:-1])] + [tr[-1]]
    top_rows.append(tr)
    bot_rows.append(br)
tip = bm.verts.new((0.0, TIP_Y, float(s_top(TIP_Y - 0.02) * 0.5 + s_bot(TIP_Y - 0.02) * 0.5)))
for i in range(len(rows) - 1):
    for j in range(N - 1):
        bm.faces.new((top_rows[i][j], top_rows[i + 1][j], top_rows[i + 1][j + 1], top_rows[i][j + 1]))
        bm.faces.new((bot_rows[i][j + 1], bot_rows[i + 1][j + 1], bot_rows[i + 1][j], bot_rows[i][j]))
for j in range(N - 1):
    bm.faces.new((top_rows[-1][j], tip, top_rows[-1][j + 1]))
    bm.faces.new((bot_rows[-1][j + 1], tip, bot_rows[-1][j]))
front = bm.faces.new([top_rows[0][j] for j in range(N - 1, -1, -1)] + [bot_rows[0][j] for j in range(1, N - 1)])
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bm.normal_update()
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
# material boundaries as real edges
for co, no in (((0, FACE_T - SEAM, 0), (0, 1, 0)), ((0, FACE_T + SEAM, 0), (0, 1, 0)), ((0, NOSE_Y, 0), (0, 1, 0)),
               ((0, FACE_T, BRASS_Z0), (0, -(BRASS_Z1 - BRASS_Z0) / (NOSE_Y - FACE_T), 1))):
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=Vector(no).normalized())
bm.normal_update()
brass_line = lambda y: BRASS_Z0 + (BRASS_Z1 - BRASS_Z0) * (y - FACE_T) / (NOSE_Y - FACE_T)
HB = (12.0, 54.0, 22.0, 40.0)        # = make_textures.HEEL_BOX
TB = (11.0, 65.0, 18.0, 44.0)        # = make_textures.TOE_BOX
uv = bm.loops.layers.uv.new("proj")
uv_sole = bm.loops.layers.uv.new("sole")
for f in bm.faces:
    cen = f.calc_center_median()
    n = f.normal
    if cen.y < 0.02 and n.y < -0.9:
        idx = I_CARBON
    elif cen.y < FACE_T - SEAM:
        idx = I_LACQ
    elif cen.y < FACE_T + SEAM:
        idx = I_SEAM
    elif cen.y > NOSE_Y or cen.z < brass_line(cen.y):
        idx = I_SOLE if (n.z < -0.25 and cen.y <= NOSE_Y + 6) else I_BRASS
    elif n.z > 0.35:
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
            q = (p.x / 4.2, p.z / 4.2)
        else:
            q = (p.x / 50.0, p.y / 50.0)
        l[uv].uv = q
        l[uv_sole].uv = ((p.x + HEAD_W / 2) / HEAD_W, 1 - p.y / HEAD_D)
head = mesh_obj("DP501_Head", bm)
for m in HEAD_MATS:
    head.data.materials.append(m)
head.data.set_sharp_from_angle(angle=math.radians(40))

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
TOP_Z = float(s_top(HOLE[1]))
P_TOP = Vector((HOLE[0], HOLE[1], TOP_Z))
P0 = P_TOP - D * (TOP_Z / D.z)                             # axis meets the sole plane here
S_HEAD = TOP_Z / D.z                                       # axis length from the sole plane to the head top


def axis(s):
    return P0 + D * s


def tube(name, s0, s1, radius_at, steps, mats, uv_fn=None, seg=96, cap_top=False):
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
nt.links.new(mix_rgb(nt, t.outputs["Alpha"], BLACK, t.outputs["Color"]), b.inputs["Base Color"])
nt.links.new(mix_f(nt, t.outputs["Alpha"], 0.0, 0.45), b.inputs["Metallic"])
M_SHAFT = m
shaft = tube("DP501_Shaft", S_HEAD - 6, CLUB_LEN - GRIP_LEN + 6, shaft_r, 260, [M_SHAFT],
             uv_fn=lambda s, v: ((WRAP[1] - s) / (WRAP[1] - WRAP[0]), v))

# ferrule: sits on the head top; visible height FERRULE_H measured vertically -> along the axis / D.z
fa = S_HEAD - 4.0
fb = S_HEAD + FERRULE_H / D.z
def ferrule_r(s):
    e = fb - s
    return FERRULE_R - (0.9 - math.sqrt(max(0.0, 0.81 - (0.9 - e) ** 2)) if e < 0.9 else 0.0)
M_FER = simple("DP501_Ferrule", BLACK, 0.0, 0.08, 1.0)
ferrule = tube("DP501_Ferrule", fa, fb, ferrule_r, 40, [M_FER])
cap_r = tube("DP501_FerruleTop", fb - 0.02, fb, lambda s: FERRULE_R - 0.9, 1, [M_FER], cap_top=True)
bc = S_HEAD + BAND_C / D.z
band = tube("DP501_FerruleBand", bc - BAND_H / 2 / D.z, bc + BAND_H / 2 / D.z, lambda s: FERRULE_R + 0.03, 3,
            [holo_band()])

# grip
G0 = CLUB_LEN - GRIP_LEN


def grip_r(s):
    e = CLUB_LEN - s                                        # mm from the grip end
    r = 14.0
    if e < 2.2:                                             # rounded end
        r = 12.2 + math.sqrt(max(0.0, 2.2 ** 2 - (2.2 - e) ** 2)) * (1.8 / 2.2)
    elif e > 250:
        r = 14.0 - 1.4 * ((e - 250) / 100) ** 1.3
    if e > GRIP_LEN - 3:                                    # lip down onto the shaft
        r = SHAFT_R1 + (r - SHAFT_R1) * max(0.0, (GRIP_LEN - e) / 3) ** 0.5
    return r


m, nt, b = principled("DP501_Grip")
ta = tex(nt, img("grip_albedo.png"), extension="REPEAT")
tb = tex(nt, img("grip_bump.png", False), extension="REPEAT")
nt.links.new(ta.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.62
b.inputs["Specular IOR Level"].default_value = 0.35
bp = node(nt, "ShaderNodeBump", Strength=0.9, Distance=0.0011)
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

# ================================================================ assembly + exports
root = link(bpy.data.objects.new("GRAZR_DP501", None))
for o in list(col.objects):
    if o is not root and o.type == "MESH":
        o.parent = root
        o.data.name = o.name
root.scale = (0.001, 0.001, 0.001)
bpy.context.view_layer.update()
print("axis meets the sole at X=%.1f (heel end 53 -> %.1f mm), club length %.0f" % (P0.x, 53 - P0.x, CLUB_LEN))
bpy.ops.file.pack_all()
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
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.053, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world
cam_data = bpy.data.cameras.new("cam")
cam_data.clip_start = 0.001
cam = link(bpy.data.objects.new("Camera", cam_data))
scene.camera = cam
CLUB = (shaft, grip, cap)


def area(name, loc, target, size, power, color=(1, 1, 1)):
    li = bpy.data.lights.new(name, "AREA")
    if isinstance(size, tuple):
        li.shape = "RECTANGLE"
        li.size, li.size_y = size
    else:
        li.size = size
    li.energy = power
    li.color = color
    ob = link(bpy.data.objects.new(name, li))
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
         ortho=None, bg=0.93):
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
    px[:, :3] = px[:, :3] * a + bg * (1 - a)
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

shot("01_hero", HC + mm(-300, -340, 230), HC + mm(4, 0, 10), 85, studio())
shot("02_face", HC + mm(0, -430, 25), HC + mm(0, 0, 4), 100, studio())
shot("03_top", HC + mm(0, 0, 460), HC, 85, studio(), up=(-1, 0, 0), head_only=True)
shot("04_back", HC + mm(80, 470, 120), HC + mm(0, 0, 8), 85, studio())
shot("05_sole", HC + mm(0, 0, -460), HC, 85, below(studio()), up=(0, -1, 0), head_only=True)
shot("06_toe", HC + mm(-440, 0, 40), HC, 90, studio(), head_only=True)
shot("07_heel", HC + mm(440, 0, 40), HC, 90, studio(), head_only=True)
mid = axis(430) * 0.001
shot("08_full", mid + Vector((-0.75, -2.3, 0.2)), mid, 85,
     [("key", mid + Vector((-0.9, -1.4, 1.2)), mid, 1.2, 90), ("fill", mid + Vector((1.2, -0.7, 0.4)), mid, 1.5, 30),
      ("rim", mid + Vector((0.3, 1.3, 0.9)), mid, 1.0, 60)], res=(1200, 1600))
sc = axis(WRAP[0] + 125) * 0.001
toe_view = Vector(FRONT) * 0.36
shot("09_shaft", sc + toe_view + mm(0, -40, 0), sc, 85,
     [("key", sc + Vector(FRONT) * 0.3 + Vector((0, -0.25, 0.15)), sc, 0.5, 9.0),
      ("fill", sc + Vector(FRONT) * 0.3 + Vector((0, 0.3, -0.05)), sc, 0.6, 4.0)],
     up=tuple(D), res=(1200, 1600))
gc = axis(CLUB_LEN - 175) * 0.001
shot("10_grip", gc + Vector(FRONT) * 0.5 + mm(0, -60, 0), gc, 85,
     [("key", gc + Vector(FRONT) * 0.4 + Vector((0, -0.3, 0.2)), gc, 0.5, 9.0),
      ("fill", gc + Vector(FRONT) * 0.3 + Vector((0, 0.35, -0.05)), gc, 0.6, 4.0)],
     up=tuple(D), res=(1200, 1600))
print("done")
