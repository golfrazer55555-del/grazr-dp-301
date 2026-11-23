"""GRAZR DP-501 head shape, pure numpy (no Blender): used by build_dp501.py and the check scripts.

The head is a closed surface over the top-view outline (top drawing). Its cross-section is the creased octagon seen
on the real head (face photo, back photo with the owner's marked lines, sole photos):

    crown (top)          slightly crowned, its centre line follows the heel drawing's top silhouette
    upper crease         where the crown meets the upper chamfer (the owner's top pink line): a wide U round the nose
                         (the crown runs on gently to the tip, so the chamfer there is ~3.6 mm tall, back photo)
    upper chamfer        35 deg on the sides (face photo), steeper round the nose
    corner line          the widest line, round 1-3 mm (the owner's middle pink line), 41 mm at the face -> 44.5 at
                         the nose tip (heel drawing)
    side wall            leans in 9 deg going down (face photo); round the nose it is the 77.5 deg back face
    lower crease         where the wall meets the sole / lower chamfer (the owner's bottom pink line, a flat arch
                         round the back); brass below it
    lower chamfer        28 deg (face photo); the flat sole between the two chamfers narrows towards the back with
                         the outline (|X| < 25.8 at the face, ~0.55 of the half width further back)
    sole                 flat, then the heel drawing's rise towards the back

Coordinates in mm: X toe (-) -> heel (+), Y face (0) -> back (+), Z sole (0) -> up.
Every surface is a function of d (distance to the outline in plan) or of X / Y, joined with C2 smooth min / max,
so the reflections stay even; normals come from the same functions.
"""
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial import cKDTree

HEAD_W, HEAD_D, HEAD_H = 106.0, 95.0, 56.0
FACE_T = 8.0
NOSE_Y = 85.5                        # brass back weight from here (back photos: ~38 mm wide at the widest line)

# ================================================================ plan outline (top drawing, unchanged)
SE_Y0, SE_N, SE_M = 26.19, 1.592, 1.6
CORNER_R = 1.0                       # small vertical round on the face plate corners
NOSE_B = 84.0
NOSE_P = (14.55217, 1.91438, -0.06561, 0.00076)
TIP_Y = HEAD_D


def _se_xy(th):
    return 53.0 * np.cos(th) ** (2 / SE_N), SE_Y0 + (HEAD_D - SE_Y0) * np.sin(th) ** (2 / SE_M)


def _nose_w(y):
    e = np.clip(HEAD_D - np.asarray(y, float), 0, None)
    return np.sqrt(np.clip(2 * NOSE_P[0] * e + NOSE_P[1] * e ** 2 + NOSE_P[2] * e ** 3 + NOSE_P[3] * e ** 4, 0, None))


def hw_core(y):
    """Half width of the outline without the face plate corner round."""
    y = np.asarray(y, float)
    t = np.clip((y - SE_Y0) / (HEAD_D - SE_Y0), 0, 1)
    w = 53.0 * np.clip(1 - t ** SE_M, 0, 1) ** (1 / SE_N)
    return np.where(y > NOSE_B, _nose_w(y), w)


def half_width(y):
    y = np.asarray(y, float)
    corner = 53.0 - CORNER_R + np.sqrt(np.clip(CORNER_R ** 2 - (CORNER_R - y) ** 2, 0, None))
    return np.where(y < CORNER_R, corner, hw_core(y))


def corner_squash(y):
    """Near the face the corner round squeezes the section sideways: x is shaped like x * k. Returns k, dk/dy."""
    y = np.asarray(y, float)
    ratio = lambda v: 53.0 / half_width(np.minimum(v, CORNER_R))
    h = 1e-5
    yl, yh = np.maximum(y - h, 0.0), y + h
    near = y < CORNER_R
    return np.where(near, ratio(y), 1.0), np.where(near, (ratio(yh) - ratio(yl)) / (yh - yl), 0.0)


_th = np.linspace(0, np.arcsin(((NOSE_B - SE_Y0) / (HEAD_D - SE_Y0)) ** (SE_M / 2)), 6000)
_w, _y = _se_xy(_th)
_u = np.linspace(np.sqrt(HEAD_D - NOSE_B), 0, 3000)[1:] ** 2
_w = np.concatenate([_w, _nose_w(HEAD_D - _u)])
_y = np.concatenate([_y, HEAD_D - _u])
_yc = np.linspace(0, SE_Y0, 2000)
_heel = np.concatenate([np.stack([hw_core(_yc), _yc], 1), np.stack([_w, _y], 1)])
OUTLINE = np.concatenate([_heel * [-1, 1], _heel[::-1][1:]])
OUTLINE = OUTLINE[np.r_[True, np.hypot(*np.diff(OUTLINE, axis=0).T) > 1e-9]]
_SA = OUTLINE[:-1]
_SD = OUTLINE[1:] - _SA
_SL2 = (_SD ** 2).sum(1)
_SN = np.stack([_SD[:, 1], -_SD[:, 0]], 1) / np.sqrt(_SL2)[:, None]      # inward unit normal of each segment
_TREE = cKDTree(OUTLINE)


def poly_dist(x, y):
    """Distance to the outline polyline (mirrored at the face plane), its gradient (inward unit vector) and the
    nearest outline point. Points on or a hair outside the outline get d = 0 and the outline's normal."""
    x = np.ravel(np.asarray(x, float))
    y = np.ravel(np.asarray(y, float))
    p = np.stack([x, np.abs(y)], 1)
    _, idx = _TREE.query(p, k=2)
    best = np.full(len(p), np.inf)
    grad = np.zeros((len(p), 2))
    near = np.zeros((len(p), 2))
    for k in range(2):
        for off in (-1, 0):
            i = np.clip(idx[:, k] + off, 0, len(_SA) - 1)
            t = np.clip(((p - _SA[i]) * _SD[i]).sum(1) / _SL2[i], 0, 1)
            q = _SA[i] + t[:, None] * _SD[i]
            v = p - q
            dd = np.hypot(v[:, 0], v[:, 1])
            on = (v * _SN[i]).sum(1) < 1e-6
            g = np.where(on[:, None], _SN[i], v / np.maximum(dd, 1e-12)[:, None])
            dd = np.where(on, 0.0, dd)
            better = dd < best
            best = np.where(better, dd, best)
            grad = np.where(better[:, None], g, grad)
            near = np.where(better[:, None], q, near)
    sgn = np.where(y < 0, -1.0, 1.0)
    grad[:, 1] *= sgn
    near[:, 1] *= sgn
    return best, grad, near


# ================================================================ side silhouettes (heel drawing, unchanged fits)
TOP_KNOTS = [(44.0, 56.0), (46.0, 56.0), (48.0, 56.0), (50.0, 55.995), (52.0, 55.884), (54.0, 55.669),
             (56.0, 55.425), (58.0, 55.168), (60.0, 54.898), (62.0, 54.615), (64.0, 54.32), (66.0, 54.006),
             (68.0, 53.674), (70.0, 53.355), (72.0, 53.01), (74.0, 52.636), (76.0, 52.25), (78.0, 51.846),
             (80.0, 51.421), (82.0, 50.968), (84.0, 50.478), (86.0, 49.947), (88.0, 49.36), (90.0, 48.80),
             (92.0, 48.45), (94.0, 48.08), (94.4, 48.0)]
# (from Y 90 the crown runs on gently: the drawing's steeper drop there is the upper chamfer round the nose tip, which
#  the back photo shows ~3.7 mm tall; the side silhouette stays within 0.7 mm of the drawing)
_tk = np.array(TOP_KNOTS)
_tcs = CubicSpline(_tk[:, 0], _tk[:, 1], bc_type=((1, 0.0), "not-a-knot"))


def top_line(y):
    """Centre line of the crown (heel drawing's top silhouette)."""
    y = np.asarray(y, float)
    return np.where(y < 44.0, 56.0, _tcs(np.clip(y, 44.0, None)))


def sole_line(y, k=0.6):
    """Centre line of the sole: flat, soft bend at Y 42.7, slightly curving rise (heel drawing)."""
    y = np.asarray(y, float)
    return k * np.logaddexp(0.0, (0.39580 * (y - 60.0) + 6.3724 + 0.001150 * (y - 60.0) ** 2) / k)


FRONT_R = 1.0                        # the face plate's front edges are rounded 1 mm


def front_round(y):
    y = np.asarray(y, float)
    return np.where(y < FRONT_R, FRONT_R - np.sqrt(np.clip(FRONT_R ** 2 - (FRONT_R - y) ** 2, 0, None)), 0.0)


# ================================================================ section (face photo fits; see SPEC.md)
P = dict(
    zc_face=41.5, zc_tip=44.5, zc_y0=45.0,        # corner line height (face photo / heel drawing's nose tip)
    k_up_side=0.745, k_up_back=1.10,              # upper chamfer slope (dz per mm inwards): 36.7 deg / 48 deg
    cot_side=6.99, cot_back=3.6, p_wall=8.0,      # side wall leans in 8.1 deg going down; back face 74 deg at the tip
    c_top=2.7, c_bot=14.0,                        # corner round: curvature radius c / 2 at the corner line
    crown=0.0014,                                 # crown drop dz = crown * x^2
    xf=25.8, k_lc=0.533, kappa=0.181, xf_c=16.64,  # lower chamfer, 28 deg: from |x| 25.8 (face photo), narrowing to
                                                   # kappa * half width + xf_c towards the back (owner's back lines)
    b_uc=4.0, b_lc_side=5.0, b_lc_back=3.5, b_flat=8.0,   # blend widths (z) of the creases
)


def smin(a, b, k):
    """C2 smooth minimum, blend width k (same units as a, b)."""
    k = np.maximum(k, 1e-9)
    h = np.clip(k - np.abs(a - b), 0, None) / k
    return np.minimum(a, b) - h ** 3 * k / 6.0


def smax(a, b, k):
    return -smin(-a, -b, k)


def zc_line(y):
    """Height of the corner (widest) line."""
    t = np.clip((np.asarray(y, float) - P["zc_y0"]) / (TIP_Y - P["zc_y0"]), 0, 1)
    s = t * t * t * (10 - 15 * t + 6 * t * t)                  # C2 smoothstep
    return P["zc_face"] + (P["zc_tip"] - P["zc_face"]) * s


def back_weight(ny):
    """0 on the straight sides, 1 where the outline faces straight back (nose); ny = outward normal's y."""
    return np.clip(ny, 0, 1) ** 2


def surfaces(x, y, want=("zt", "zb")):
    """Top and bottom surface heights at plan points (x, y) inside the outline (vectorised). Returns a dict with
    zt, zb and helpers: d, parts of the top (chamfer, crown) and bottom (wall, lower)."""
    x = np.ravel(np.asarray(x, float))
    y = np.ravel(np.asarray(y, float))
    k, _ = corner_squash(y)
    xc = x * k                                                  # sideways squeeze at the face plate corners
    d, g, q = poly_dist(xc, y)
    ny = -g[:, 1]                                               # outward normal's y (g points inwards)
    wb = back_weight(ny)
    zc = zc_line(q[:, 1])
    kup = P["k_up_side"] + (P["k_up_back"] - P["k_up_side"]) * wb
    # the wall keeps the sides' slope well round the nose (the brass weight's sides are a vertical plane on the back
    # photo) and leans back only near the tip
    cot = P["cot_side"] + (P["cot_back"] - P["cot_side"]) * np.clip(ny, 0, 1) ** P["p_wall"]
    cham = zc + np.sqrt(P["c_top"] * d + (kup * d) ** 2)
    crown = top_line(y) - P["crown"] * xc ** 2
    # the blend never reaches the corner line itself (near the nose tip the crown comes down close to it), so the
    # top and bottom surfaces still meet exactly at the outline
    kuc = smin(np.full_like(crown, P["b_uc"]), 0.8 * np.clip(crown - zc, 0, None), 0.5)
    zt = smin(cham, crown, kuc)
    wall = zc - np.sqrt(P["c_bot"] * d + (cot * d) ** 2)
    base = sole_line(y)
    xf = smin(np.full_like(y, P["xf"]), P["kappa"] * hw_core(y) + P["xf_c"], 1.0)
    bf = smin(np.full_like(y, P["b_flat"]), 0.8 * P["k_lc"] * xf, 0.5)      # the blend never reaches the centre line
    lower = smax(base, base + P["k_lc"] * (np.abs(xc) - xf), bf)
    blc = P["b_lc_side"] + (P["b_lc_back"] - P["b_lc_side"]) * wb
    blc = smin(blc, 0.8 * np.clip(zc - lower, 0, None), 0.5)
    zb = smax(wall, lower, blc)
    # the face plate's front edges: squeeze the section vertically about its middle over the first millimetre
    fr = front_round(y)
    sq = 1 - 2 * fr / HEAD_H
    zt = 28.0 + (zt - 28.0) * sq
    zb = 28.0 + (zb - 28.0) * sq
    return dict(zt=zt, zb=zb, d=d, cham=cham, crown=crown, wall=wall, lower=lower, zc=zc, grad=g, ny=ny)
