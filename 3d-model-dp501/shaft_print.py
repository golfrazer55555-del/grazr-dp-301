"""DP-501 shaft print, redrawn as clean artwork at 30 px/mm (the old texture was traced from a 2.4 px/mm drawing).

  python3 3d-model-dp501/shaft_print.py            # writes textures/shaft_wrap.png + shaft_wrap_metal.png
  python3 3d-model-dp501/shaft_print.py --check    # also a flat preview (check/shaft_print_flat.png)

Layout: the owner's unrolled shaft drawing (shaft-front-closeup-design.jpg, 250 mm band) and the print mock-up
(shaft.jpg), corrected to the real club where the photos differ (aim lines run to 175 mm past the hex, two-tone
gold / silver leaves, back text as printed).  Measured from those images:

  GR mark            u 400.0-425.9 (mark_white.png: white part = G + top/right of the hexagon, gold part = R +
                     left/bottom, as on the photos)
  crown + rings      crown 431.6-438.3, gold ring 438.2-441.05, silver ring 442.7-445.2 (all the way round)
  GRAZR              u 452.7-500.1, 8.2 mm tall (wordmark_white.png)
  knot               hex centre u 536: white hex ring (apothem 1.65-2.36), silver ring (4.0-4.6); outside the hexagon
                     (apothem 4.6) and along the six spokes the print is a set of offset lines - gold 0.43-1.05 mm,
                     silver 1.96-3.06 mm - so the corners mitre exactly as printed
  spokes             line to the head (tip at u 711), stem to the grip with a square end (u 510.56), four arms at
                     60 deg to the shaft reaching 23.5 mm (to about 126 deg round the shaft), notched tips
  leaves             maple leaf traced from the back close-up photo (textures/shaft_leaf.json), placed where the
                     drawing has them (template fitted to each, IoU 0.80-0.87), alternating gold / silver along the
                     shaft as on the club; crescent swooshes between; the pattern carries on along the longer line
  back               '- PREMIUM MAPLE TREE -' (squared capitals, 2.74 mm) on the back line behind the hex, with
                     'DESIGN BY GRAZR STUDIO' beside it, as on shaft-back-closeup.png

Coordinates: u = mm from the grip end along the shaft; c = mm round the shaft from the front of the print (the
toe side), positive downwards in the image; the full circumference is CD mm (the drawing's, 57.7 mm at the hex).
Image x = u, y = c (the back seam at the top / bottom edges), the same orientation as the old shaft_wrap.png.
"""
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEX = os.path.join(HERE, "textures")
LOGO_TEX = os.path.join(ROOT, "3d-model", "textures")
F_BOLD = os.path.join(HERE, "fonts", "montserrat-latin-800-normal.woff")

PX = 30.0                                   # px per mm
U0, U1 = 385.0, 730.0                       # printed span (mm from the grip end)
CD = 57.7                                   # circumference the drawing is laid out on (mm)
W = int(round((U1 - U0) * PX))
H = int(round(CD * PX))
SS = 4                                      # supersampling for filled shapes

GOLD, SILVER, WHITE = 0, 1, 2
INK_RGB = {GOLD: (214, 182, 112), SILVER: (176, 178, 180), WHITE: (240, 240, 236)}
INK_METAL = {GOLD: 0.55, SILVER: 0.6, WHITE: 0.0}

HEX_U = 536.0
LINE_TIP = HEX_U + 175.0                    # the aim line runs on to here on the club (the drawing stops at 650)
STEM_END = 510.56
ARM_LEN = 23.5
G_IN, G_OUT, S_IN, S_OUT = 0.43, 1.05, 1.96, 3.06
HEX_A = 4.6


class Canvas:
    def __init__(self):
        self.cov = np.zeros((3, H, W), np.float32)

    def paint(self, ink, cov, x0, y0):
        """Lay coverage `cov` (patch at image x0, y0; rows wrap round the shaft) of `ink` (None = black)."""
        h, w = cov.shape
        x1 = min(W, x0 + w)
        if x1 <= max(0, x0):
            return
        sx = slice(max(0, x0), x1)
        cx = slice(max(0, x0) - x0, x1 - x0)
        ys = (np.arange(h) + y0) % H
        # split into contiguous runs of rows
        starts = np.r_[0, np.where(np.diff(ys) != 1)[0] + 1]
        ends = np.r_[starts[1:], h]
        for a, b in zip(starts, ends):
            ry = slice(ys[a], ys[a] + (b - a))
            c = cov[a:b, cx]
            for k in range(3):
                self.cov[k, ry, sx] *= 1.0 - c
            if ink is not None:
                self.cov[ink, ry, sx] += c


def px_of(u, c):
    return (u - U0) * PX, (c + CD / 2) * PX


def fill_polys(polys_mm, pad=2):
    """Rasterise polygons (lists of (u, c) mm) with supersampling. Returns coverage patch and its x0, y0."""
    allp = np.concatenate([np.asarray(p, float) for p in polys_mm])
    xs, ys = px_of(allp[:, 0], allp[:, 1])
    x0, y0 = int(math.floor(xs.min())) - pad, int(math.floor(ys.min())) - pad
    w, h = int(math.ceil(xs.max())) - x0 + pad, int(math.ceil(ys.max())) - y0 + pad
    m = np.zeros((h * SS, w * SS), np.uint8)
    pts = []
    for p in polys_mm:
        p = np.asarray(p, float)
        px, py = px_of(p[:, 0], p[:, 1])
        pts.append(np.round(np.stack([(px - x0) * SS, (py - y0) * SS], 1) * 16).astype(np.int32))
    cv2.fillPoly(m, pts, 255, lineType=cv2.LINE_8, shift=4)
    cov = cv2.resize(m.astype(np.float32) / 255.0, (w, h), interpolation=cv2.INTER_AREA)
    return cov, x0, y0


def band_of_polygon(poly_mm, inner):
    """Coverage of the strip inside polygon `poly_mm` within `inner` mm of its edge (an inward outline)."""
    allp = np.asarray(poly_mm, float)
    xs, ys = px_of(allp[:, 0], allp[:, 1])
    pad = 3
    x0, y0 = int(math.floor(xs.min())) - pad, int(math.floor(ys.min())) - pad
    w, h = int(math.ceil(xs.max())) - x0 + pad, int(math.ceil(ys.max())) - y0 + pad
    m = np.zeros((h * SS, w * SS), np.uint8)
    pts = np.round(np.stack([(xs - x0) * SS, (ys - y0) * SS], 1) * 16).astype(np.int32)
    cv2.fillPoly(m, [pts], 255, lineType=cv2.LINE_8, shift=4)
    d = cv2.distanceTransform(m, cv2.DIST_L2, 5) / (SS * PX)          # mm to the outside
    band = ((m > 0) & (d <= inner)).astype(np.float32)
    return cv2.resize(band, (w, h), interpolation=cv2.INTER_AREA), x0, y0


def edge(d, lo, hi):
    """Anti-aliased coverage of lo <= d <= hi for a distance field d (mm), one-pixel ramps."""
    return np.clip((d - lo) * PX + 0.5, 0, 1) - np.clip((d - hi) * PX + 0.5, 0, 1)


def rot(p, ang):
    a = math.radians(ang)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return np.asarray(p, float) @ R.T


# ------------------------------------------------------------------ parts
def rings(cv):
    for ink, a, b in ((GOLD, 438.2, 441.05), (SILVER, 442.7, 445.2)):
        x0, x1 = (a - U0) * PX, (b - U0) * PX
        xi = int(math.floor(x0))
        w = int(math.ceil(x1)) - xi
        xx = np.arange(w) + xi + 0.5
        row = np.clip(xx - x0 + 0.5, 0, 1) - np.clip(xx - x1 + 0.5, 0, 1)
        cv.paint(ink, np.repeat(row[None, :].astype(np.float32), H, 0), xi, 0)


def crown(cv):
    half = [(431.6, 0.0), (435.0, -2.25), (435.15, -3.4), (435.05, -5.3), (435.0, -6.4), (435.5, -6.5),
            (436.2, -5.9), (437.05, -5.15), (437.8, -4.7), (438.4, -4.7), (438.4, -3.62), (437.9, -3.62),
            (436.3, -2.8), (435.15, -2.1), (432.3, 0.0)]
    other = [(u, -c) for u, c in reversed(half[1:-1])]
    chevron = half + other
    inner = [(434.42, 0.0), (438.4, -2.6), (438.4, 2.6)]
    cov, x0, y0 = fill_polys([chevron])
    cv.paint(GOLD, cov, x0, y0)
    cov, x0, y0 = fill_polys([inner])
    cv.paint(GOLD, cov, x0, y0)


def mark(cv):
    """GR mark: upright on the club (grip up), so turned a quarter anticlockwise into the image."""
    al = np.asarray(Image.open(os.path.join(LOGO_TEX, "mark_white.png")).getchannel("A")).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats((al > 8).astype(np.uint8))
    big = sorted(range(1, n), key=lambda i: -st[i][4])[:2]
    # white part: the one whose box starts further right (G + top / right of the hexagon)
    white = max(big, key=lambda i: st[i][0])
    ys, xs = np.where(al > 8)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    length = 24.6                                                # along the shaft (the mark's height)
    s = length / (box[3] - box[1])                               # mm per source px
    width = (box[2] - box[0]) * s
    for comp, ink in ((white, WHITE), (None, GOLD)):
        m = al.astype(np.float32) / 255.0
        lab_d = cv2.dilate((lab == comp).astype(np.uint8), np.ones((5, 5), np.uint8)) if comp else None
        if comp:
            m = m * lab_d
        else:
            m = m * (1 - cv2.dilate((lab == white).astype(np.uint8), np.ones((5, 5), np.uint8)))
        m = m[box[1]:box[3], box[0]:box[2]]
        m = np.rot90(m, 1)                                       # anticlockwise: top of the mark -> grip side
        w_px, h_px = int(round(length * PX)), int(round(width * PX))
        cov = cv2.resize(np.ascontiguousarray(m), (w_px, h_px), interpolation=cv2.INTER_AREA)
        x0, y0 = px_of(399.5, -width / 2)
        cv.paint(ink, cov, int(round(x0)), int(round(y0)))


def wordmark(cv):
    al = np.asarray(Image.open(os.path.join(LOGO_TEX, "wordmark_white.png")).getchannel("A")).astype(np.float32) / 255
    ys, xs = np.where(al > 0.03)
    al = al[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    length, height = 47.4, 8.2
    cov = cv2.resize(al, (int(round(length * PX)), int(round(height * PX))), interpolation=cv2.INTER_AREA)
    x0, y0 = px_of(452.7, -height / 2)
    cv.paint(GOLD, cov, int(round(x0)), int(round(y0)))


# knot: hexagon + six spokes as one distance field
def hex_metric(du, dc):
    """max over the hexagon's edge normals (vertices along u): apothem-type distance."""
    out = None
    for a in (30, 90, 150, 210, 270, 330):
        r = math.radians(a)
        v = du * math.cos(r) + dc * math.sin(r)
        out = v if out is None else np.maximum(out, v)
    return out


ARM_DIRS = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in (60, 120, 240, 300)]
CAP_BACK = 9.0                              # the notched ends take over this far before the tip


def knot(cv):
    ua, ub = STEM_END - 4.0, LINE_TIP + 1.0
    x0 = int(math.floor((ua - U0) * PX))
    x1 = int(math.ceil((ub - U0) * PX))
    c_lim = ARM_LEN * math.sin(math.radians(60)) + 5.0
    y0 = int(math.floor((-c_lim + CD / 2) * PX))
    y1 = int(math.ceil((c_lim + CD / 2) * PX))
    xx = (np.arange(x0, x1) + 0.5) / PX + U0
    yy = (np.arange(y0, y1) + 0.5) / PX - CD / 2
    du = (xx - HEX_U)[None, :].astype(np.float32)
    dc = yy[:, None].astype(np.float32)
    du, dc = np.broadcast_to(du, (len(yy), len(xx))), np.broadcast_to(dc, (len(yy), len(xx)))
    INF = np.float32(1e3)
    hm = hex_metric(du, dc)
    d = np.maximum(hm - HEX_A, 0)
    # line to the head (its notched end is drawn separately from LINE_TIP - CAP_BACK on)
    t_line = du
    d = np.minimum(d, np.where((t_line >= 0) & (du <= LINE_TIP - CAP_BACK - HEX_U + 0.5), np.abs(dc), INF))
    # stem to the grip, square end
    d = np.minimum(d, np.where(du <= 0, np.maximum(np.abs(dc), (STEM_END - HEX_U) - du), INF))
    # arms
    for vx, vy in ARM_DIRS:
        t = du * vx + dc * vy
        s = np.abs(du * vy - dc * vx)
        d = np.minimum(d, np.where((t >= 0) & (t <= ARM_LEN - CAP_BACK + 0.5), s, INF))
    inside = np.clip((HEX_A - hm) * PX + 0.5, 0, 1)                # inside the hexagon: its own rings
    gold = edge(d, G_IN, G_OUT) * (1 - inside)
    silver = edge(d, S_IN, S_OUT) * (1 - inside) + inside * edge(hm, 4.0, 4.6)
    white = inside * edge(hm, 1.65, 2.36)
    # the knot owns its outline and everything inside it (leaves never run under the lines)
    owned = np.maximum(np.clip((S_OUT + 0.25 - d) * PX + 0.5, 0, 1), inside)
    for k, c in ((GOLD, gold), (SILVER, silver), (WHITE, white)):
        cv.cov[k, y0:y1, x0:x1] = cv.cov[k, y0:y1, x0:x1] * (1 - owned) + c
    # notched ends of the line and the four arms
    cap(cv, (LINE_TIP, 0.0), (1.0, 0.0))
    for vx, vy in ARM_DIRS:
        cap(cv, (HEX_U + vx * ARM_LEN, vy * ARM_LEN), (vx, vy))


def cap(cv, tip, v):
    """Notched end: a silver outline 1.1 mm wide round an arrow with two notches; the gold lines end in a small
    notched point inside it (mock-up shaft.jpg)."""
    vx, vy = v
    nx, ny = -vy, vx

    def tr(pts):
        return [(tip[0] + t * vx + s * nx, tip[1] + t * vy + s * ny) for t, s in pts]

    back = -CAP_BACK - 3.0                       # polygons start well inside the field; only t > -CAP_BACK is used
    outer = [(back, -S_OUT), (-2.3, -S_OUT), (-3.6, -1.65), (0.0, 0.0), (-3.6, 1.65), (-2.3, S_OUT), (back, S_OUT)]
    gold = [(back, -G_OUT), (-7.3, -G_OUT), (-7.75, -0.5), (-5.9, 0.0), (-7.75, 0.5), (-7.3, G_OUT), (back, G_OUT)]

    def beyond(x0, y0, h, w):
        xx = (np.arange(w) + x0 + 0.5) / PX + U0 - tip[0]
        yy = (np.arange(h) + y0 + 0.5) / PX - CD / 2 - tip[1]
        t = xx[None, :] * vx + yy[:, None] * vy
        return np.clip((t + CAP_BACK) * PX + 0.5, 0, 1).astype(np.float32)

    cov, x0, y0 = fill_polys([tr(outer)])
    cv.paint(None, cov * beyond(x0, y0, *cov.shape), x0, y0)          # the end of the field, then the outlines
    cov, x0, y0 = band_of_polygon(tr(outer), S_OUT - S_IN)
    cv.paint(SILVER, cov * beyond(x0, y0, *cov.shape), x0, y0)
    cov, x0, y0 = band_of_polygon(tr(gold), G_OUT - G_IN)
    cv.paint(GOLD, cov * beyond(x0, y0, *cov.shape), x0, y0)


# ------------------------------------------------------------------ leaves
LEAF = json.load(open(os.path.join(TEX, "shaft_leaf.json")))
LEAF_POLY = np.array(LEAF["poly"])
LEAF_VEIN = np.array(LEAF["vein"])


def crescent(length, bend=0.35, thick=0.18, n=48):
    s = np.linspace(-0.5, 0.5, n)
    x, y = s * length, bend * length * (1 - (2 * s) ** 2)
    th = thick * length * np.sin(np.pi * (s + 0.5)) ** 0.8 / 2
    dx, dy = np.gradient(x), np.gradient(y)
    nn = np.hypot(dx, dy)
    nx, ny = -dy / nn, dx / nn
    p = np.concatenate([np.stack([x + nx * th, y + ny * th], 1), np.stack([x - nx * th, y - ny * th], 1)[::-1]])
    return p - p.mean(0)


SWOOSH = crescent(1.0)

# (u, c-angle deg, kind, mirror, rotation deg, scale, ink) for the upper side; the lower side is the mirror image.
# From the drawing (template fits) - upper side = negative angles; the pattern is carried on past the drawing's end.
LEAVES_UPPER = [
    # beside GRAZR: the front-facing leaves as photographed (shaft-front-closeup.png), the drawing's big leaf and
    # swooshes further round the sides
    (465.5, -72.0, "leaf", 1, 350, 1.20, SILVER),
    (462.0, -108.0, "leaf", 1, 340, 1.45, GOLD),
    (488.5, -68.0, "leaf", 1, 350, 1.55, SILVER),
    (511.5, -62.0, "leaf", 1, 356, 1.20, GOLD),
    # round the back sides (shaft-back-closeup.png): big silver leaves and gold sprigs either side of the text
    (484.0, -122.0, "leaf", 1, 10, 1.55, SILVER),
    (509.0, -118.0, "leaf", 1, 20, 1.15, GOLD),
    (566.0, -122.0, "leaf", 1, 10, 1.55, SILVER),
    (591.0, -118.0, "leaf", 1, 20, 1.15, GOLD),
    # along the aim line the club has an even run of leaves, measured on shaft-front-closeup.png (21 mm apart,
    # silver / gold in turn, about 14 mm long, pointing along the shaft) - the drawing's shrinking run is not used
    (564.0, -64.5, "leaf", 1, 350, 1.59, SILVER),
    (573.5, -72.0, "swoosh", 1, 300, 5.4, GOLD),
    (582.0, -63.0, "leaf", 1, 356, 1.61, GOLD),
    (594.0, -71.0, "swoosh", 1, 296, 5.4, GOLD),
    (606.5, -63.5, "leaf", 1, 350, 1.46, SILVER),
    (615.5, -71.0, "swoosh", 1, 300, 5.2, GOLD),
    (624.6, -63.0, "leaf", 1, 356, 1.46, GOLD),
    (637.5, -71.0, "swoosh", 1, 296, 5.0, GOLD),
    (649.7, -64.0, "leaf", 1, 350, 1.28, SILVER),
    (659.0, -70.0, "swoosh", 1, 300, 4.8, GOLD),
    (668.6, -62.0, "leaf", 1, 356, 1.22, GOLD),
    (680.0, -69.0, "swoosh", 1, 296, 4.6, GOLD),
    (689.5, -63.0, "leaf", 1, 350, 1.04, SILVER),
]
# on the back line, before and after the text: one gold leaf each (the drawing shows each twice, once on either
# edge of the unrolled band - the same leaf; shaft-back-closeup.png has one, stem towards the head side)
LEAVES_BACK = [
    (497.5, 180.0, "leaf", 1, 270, 0.85, GOLD),
    (574.5, 180.0, "leaf", 1, 270, 0.85, GOLD),
]


def deg2c(a):
    return a / 360.0 * CD


def place(kind, mir, ang, sc, u, c):
    base = LEAF_POLY if kind == "leaf" else SWOOSH
    p = rot(base * np.array([mir, 1.0]), ang) * sc
    return p + np.array([u, c])


def leaves(cv):
    items = []
    for u, a, kind, mir, ang, sc, ink in LEAVES_UPPER:
        c = deg2c(a)
        items.append((kind, mir, ang, sc, u, c, ink))
        items.append((kind, -mir, 180 - ang, sc, u, -c, ink))          # mirror image across the front line
    for u, a, kind, mir, ang, sc, ink in LEAVES_BACK:
        items.append((kind, mir, ang, sc, u, deg2c(a), ink))
    for kind, mir, ang, sc, u, c, ink in items:
        p = place(kind, mir, ang, sc, u, c)
        cov, x0, y0 = fill_polys([p])
        cv.paint(ink, cov, x0, y0)
        if kind == "leaf":
            v = rot(LEAF_VEIN * np.array([mir, 1.0]), ang) * sc + np.array([u, c])
            vein(cv, v, LEAF["vein_width"] * max(0.8, sc))


def vein(cv, pts_mm, width):
    """Dark vein: a tapered stroke along the leaf's mid-line."""
    n = len(pts_mm)
    d = np.gradient(pts_mm, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    w = width / 2 * np.sin(np.linspace(0.15, 0.85, n) * np.pi) ** 0.5
    poly = np.concatenate([pts_mm + nrm * w[:, None], (pts_mm - nrm * w[:, None])[::-1]])
    cov, x0, y0 = fill_polys([poly])
    cv.paint(None, cov, x0, y0)


# ------------------------------------------------------------------ back text
def squared_glyph(ch, h, t):
    """Rectangles for the squared capitals of the back print ('M' with a full middle stem, flat-topped 'A')."""
    w = h
    R = []
    if ch == "P":
        R = [(0, 0, t, h), (0, 0, w, t), (w - t, 0, w, h * 0.55), (0, h * 0.55 - t, w, h * 0.55)]
    elif ch == "R":
        R = [(0, 0, t, h), (0, 0, w, t), (w - t, 0, w, h * 0.55), (0, h * 0.55 - t, w, h * 0.55),
             (w - t, h * 0.55 - t, w, h)]
    elif ch == "E":
        R = [(0, 0, t, h), (0, 0, w, t), (0, h / 2 - t / 2, w * 0.86, h / 2 + t / 2), (0, h - t, w, h)]
    elif ch == "M":
        R = [(0, 0, t, h), (0, 0, w, t), (w - t, 0, w, h), (w / 2 - t / 2, 0, w / 2 + t / 2, h)]
    elif ch == "I":
        w = t
        R = [(0, 0, t, h)]
    elif ch == "U":
        R = [(0, 0, t, h), (w - t, 0, w, h), (0, h - t, w, h)]
    elif ch == "A":
        R = [(0, 0, t, h), (0, 0, w, t), (w - t, 0, w, h), (0, h * 0.55 - t, w, h * 0.55)]
    elif ch == "L":
        w = h * 0.95
        R = [(0, 0, t, h), (0, h - t, w, h)]
    elif ch == "T":
        R = [(0, 0, w, t), (w / 2 - t / 2, 0, w / 2 + t / 2, h)]
    elif ch == "-":
        w = h * 0.95
        R = [(0, h / 2 - t * 0.45, w, h / 2 + t * 0.45)]
    return R, w


def text_mask(px_per_mm):
    """'- PREMIUM MAPLE TREE -' at 2.74 mm, 0.41 mm letter gap, 1.47 mm word gap; returns mask and size (mm)."""
    h, t, gap, wgap = 2.74, 0.56, 0.41, 1.47
    x = 0.0
    rects = []
    for word in ("-", "PREMIUM", "MAPLE", "TREE", "-"):
        for ch in word:
            R, w = squared_glyph(ch, h, t)
            rects += [(x + a, b, x + c, d) for a, b, c, d in R]
            x += w + gap
        x += wgap - gap
    L = x - wgap
    k = px_per_mm
    m = np.zeros((int(math.ceil(h * k)) + 4, int(math.ceil(L * k)) + 4), np.uint8)
    for a, b, c, d in rects:
        cv2.rectangle(m, (int(round(a * k)) + 2, int(round(b * k)) + 2), (int(round(c * k)) + 1, int(round(d * k)) + 1),
                      255, -1)
    r = max(1, int(round(t * 0.35 * k)))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    return m, (m.shape[1] / k, m.shape[0] / k)


def back_text(cv):
    k = PX * SS
    m, (L, hh) = text_mask(k)
    cov = cv2.resize(m.astype(np.float32) / 255.0, (int(round(L * PX)), int(round(hh * PX))), interpolation=cv2.INTER_AREA)
    uc = HEX_U
    x0 = int(round((uc - L / 2 - U0) * PX))
    # centred on the back line (the image's top / bottom edge); Canvas.paint wraps the rows
    y0 = int(round(H - hh * PX / 2))
    cv.paint(GOLD, cov, x0, y0)
    # DESIGN BY GRAZR STUDIO, 3.5 mm to the side, centred with it, 32.2 mm long
    f = ImageFont.truetype(F_BOLD, 400)
    bb = f.getbbox("DESIGN BY GRAZR STUDIO")
    im = Image.new("L", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), 0)
    ImageDraw.Draw(im).text((10 - bb[0], 10 - bb[1]), "DESIGN BY GRAZR STUDIO", font=f, fill=255)
    a = np.asarray(im).astype(np.float32) / 255
    ys, xs = np.where(a > 0.03)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    L2 = 32.2
    h2 = L2 * a.shape[0] / a.shape[1]
    cov = cv2.resize(a, (int(round(L2 * PX)), int(round(h2 * PX))), interpolation=cv2.INTER_AREA)
    x0 = int(round((uc - L2 / 2 - U0) * PX))
    y0 = int(round((3.5 - h2 / 2) * PX))
    cv.paint(GOLD, cov, x0, y0)


# ------------------------------------------------------------------ build
def build():
    cv = Canvas()
    rings(cv)
    crown(cv)
    mark(cv)
    wordmark(cv)
    leaves(cv)
    knot(cv)
    back_text(cv)
    cov = np.clip(cv.cov, 0, 1)
    alpha = np.clip(cov.sum(0), 0, 1)
    rgb = np.zeros((H, W, 3), np.float32)
    metal = np.zeros((H, W), np.float32)
    for k in range(3):
        rgb += cov[k][..., None] * (np.array(INK_RGB[k], np.float32) / 255.0)
        metal += cov[k] * INK_METAL[k]
    a = np.maximum(alpha, 1e-6)[..., None]
    rgb = np.where(alpha[..., None] > 0, rgb / a, 0)
    metal = np.where(alpha > 0, metal / np.maximum(alpha, 1e-6), 0)
    # the first / last columns stay clear so the texture's clamped edges are plain lacquer
    alpha[:, :2] = alpha[:, -2:] = 0
    out = np.dstack([rgb, alpha])
    Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(TEX, "shaft_wrap.png"),
                                                                                optimize=True)
    Image.fromarray((np.clip(metal, 0, 1) * 255 + 0.5).astype(np.uint8), "L").save(
        os.path.join(TEX, "shaft_wrap_metal.png"), optimize=True)
    print("shaft_wrap.png", W, "x", H)
    return out


if __name__ == "__main__":
    out = build()
    if "--check" in sys.argv:
        bg = np.array([0.05, 0.05, 0.07], np.float32)
        flat = out[..., :3] * out[..., 3:] + bg * (1 - out[..., 3:])
        os.makedirs(os.path.join(HERE, "check"), exist_ok=True)
        im = Image.fromarray((flat * 255 + 0.5).astype(np.uint8))
        im.resize((W // 4, H // 4), Image.LANCZOS).save(os.path.join(HERE, "check", "shaft_print_flat.png"))
