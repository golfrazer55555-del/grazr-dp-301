"""Textures for the GRAZR DP-501 model, built from the owner's design drawings (SPEC.md).

  python3 3d-model-dp501/make_textures.py

Writes textures/:
  top_decal.png      top graphic, planar from above (U = Y/95, V = 1 - (X+53)/106), 20 px/mm
  side_heel.png      GRAZR / GOLF RAZER          box HEEL_BOX (Y0, Y1, Z0, Z1)
  side_toe.png       PARKER 300 UNIT / LIMITED EDITION + two-tone GR   box TOE_BOX
  sole_engrave.png   sand-blasted engraving mask, planar from below (U = (X+53)/106, V = 1 - Y/95)
  sole_black.png     black-filled DP-501
  sole_rings.png     screw outlines
  shaft_wrap.png     250 mm graphic band, U along the shaft (grip side = 0), V around (front = 0.5)
  grip_albedo.png / grip_bump.png / grip_cap.png
  carbon.png         plain-weave tile (R = warp mask, G = tow height, B = fibre streaks), 2 x 2 cells of 2.15 mm
  carbon_shade.png   albedo shade of the weave, from the owner's face photo (carbon_photo_tile.png)
"""
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "grazr dp-501 parkgolf photo")
TEX = os.path.join(HERE, "textures")
LOGO_TEX = os.path.join(ROOT, "3d-model", "textures")          # GR mark + GRAZR wordmark (white on transparent)
F_SANS = os.path.join(ROOT, "3d-model", "fonts", "Montserrat_500Medium.ttf")
F_BLOCK = os.path.join(ROOT, "3d-model", "fonts", "AsapCondensed_800ExtraBold.ttf")

HEAD_W, HEAD_D = 106.0, 95.0
HEEL_BOX = (12.0, 54.0, 22.0, 40.0)        # Y0, Y1, Z0, Z1 (mm) covered by side_heel.png
TOE_BOX = (11.0, 65.0, 18.0, 44.0)
GOLD = (196, 162, 98)                       # printed gold (PANTONE 4515 C)
WHITE = (242, 242, 240)


def load(name):
    return np.asarray(Image.open(os.path.join(SRC, name)).convert("RGB")).astype(np.float32) / 255.0


def smooth_alpha(a, lo=0.35, hi=0.65):
    t = np.clip((a - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def sample(img, xs, ys):
    """Bilinear sample of a 2D/3D array at float pixel coords."""
    return np.stack([ndimage.map_coordinates(img[..., c], [ys, xs], order=1, mode="nearest")
                     for c in range(img.shape[2])], -1) if img.ndim == 3 else \
        ndimage.map_coordinates(img, [ys, xs], order=1, mode="nearest")


def logo_masks():
    mark = np.asarray(Image.open(os.path.join(LOGO_TEX, "mark_white.png")).getchannel("A"))
    word = np.asarray(Image.open(os.path.join(LOGO_TEX, "wordmark_white.png")).getchannel("A"))
    return Image.fromarray(mark), Image.fromarray(word)


def text_mask(txt, path, px, track=0.0):
    f = ImageFont.truetype(path, px)
    w = int(f.getlength(txt) + track * px * len(txt) + px)
    im = Image.new("L", (w, int(px * 1.6)), 0)
    d = ImageDraw.Draw(im)
    x = px * 0.3
    for ch in txt:
        d.text((x, 0), ch, font=f, fill=255)
        x += f.getlength(ch) + track * px
    return im.crop(im.getbbox())


def place(canvas, mask, box_mm, cx_mm, cy_mm, w_mm=None, h_mm=None, ppm=40):
    """Paste a mask into an L canvas: box_mm = (u0, v0) of the canvas origin in mm, image y grows downward."""
    if w_mm is not None and h_mm is not None:
        size = (int(w_mm * ppm), int(h_mm * ppm))
    elif w_mm is not None:
        size = (int(w_mm * ppm), max(1, int(mask.height * w_mm * ppm / mask.width)))
    else:
        size = (max(1, int(mask.width * h_mm * ppm / mask.height)), int(h_mm * ppm))
    m = mask.resize(size, Image.LANCZOS)
    x = int(round((cx_mm - box_mm[0]) * ppm - m.width / 2))
    y = int(round((cy_mm - box_mm[1]) * ppm - m.height / 2))
    canvas.paste(255, (x, y), m)
    return m


# ------------------------------------------------------------------ top graphic
def top_decal(ppm=20):
    a = load("head-top-design.jpg")
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    white = np.clip((a.min(2) - 0.62) / 0.16, 0, 1)
    gold = np.clip((r - b - 0.10) / 0.12, 0, 1) * np.clip((r - 0.35) / 0.2, 0, 1) * \
        np.clip((g / np.maximum(r, 1e-3) - 0.55) / 0.1, 0, 1)
    art = np.maximum(white, gold)
    art[:, 748:] = 0                                      # brass nose is a separate part
    inside = (a.max(2) < 0.80) | (art > 0.2)
    inside = ndimage.binary_fill_holes(ndimage.binary_closing(a.min(2) < 0.75, iterations=3))
    inside = ndimage.binary_erosion(inside, iterations=6)
    art = art * inside
    white = white * inside
    x0, x1, axis = 167.0, 858.0, 444.5                    # face edge, nose tip, symmetry row (X = 0)
    sy = (x1 - x0) / HEAD_D                                # px per mm along Y
    sx = (826.0 - 64.0) / HEAD_W                           # px per mm along X
    # the graphic is mirror-symmetric about X = 0: rebuild the heel half (hidden under the drawn shaft hole)
    # from the toe half
    H = a.shape[0]
    ys_up = np.arange(0, int(axis) + 1)
    for y in range(int(axis) + 1, H):
        ym = 2 * axis - y
        if 0 <= ym < H:
            yi = int(math.floor(ym)); t = ym - yi
            art[y] = art[yi] * (1 - t) + art[min(yi + 1, H - 1)] * t
            white[y] = white[yi] * (1 - t) + white[min(yi + 1, H - 1)] * t
    W_, H_ = int(HEAD_D * ppm), int(HEAD_W * ppm)
    Y = (np.arange(W_) + 0.5) / ppm
    X = HEAD_W / 2 - (np.arange(H_) + 0.5) / ppm          # image top = toe (X = -53) ... careful: V = 1 - (X+53)/106
    X = -HEAD_W / 2 + (np.arange(H_) + 0.5) / ppm         # row 0 = toe
    XX, YY = np.meshgrid(X, Y, indexing="ij")
    px, py = x0 + YY * sy, axis + XX * sx
    al = smooth_alpha(sample(art, px, py), 0.3, 0.6)
    wh = sample(white, px, py) > 0.45
    col = np.where(wh[..., None], np.array(WHITE, np.float32) / 255, np.array(GOLD, np.float32) / 255)
    out = np.dstack([col, al])
    Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(TEX, "top_decal.png"))


# ------------------------------------------------------------------ side lettering
def side_heel(ppm=40):
    Y0, Y1, Z0, Z1 = HEEL_BOX
    W_, H_ = int((Y1 - Y0) * ppm), int((Z1 - Z0) * ppm)
    canvas = Image.new("L", (W_, H_), 0)
    _, word = logo_masks()
    # image x = Y - Y0, image y = Z1 - Z  (viewed from the heel, face on the left)
    place(canvas, word, (Y0, 0), (15.8 + 50.0) / 2, Z1 - (30.4 + 36.5) / 2, w_mm=34.2, ppm=ppm)
    sub = text_mask("GOLF RAZER", F_SANS, 240, track=0.42)
    place(canvas, sub, (Y0, 0), (15.8 + 50.0) / 2, Z1 - (26.3 + 28.9) / 2, w_mm=34.2, h_mm=2.6, ppm=ppm)
    rgba = Image.new("RGBA", canvas.size, GOLD + (0,))
    rgba.putalpha(canvas)
    rgba.save(os.path.join(TEX, "side_heel.png"))


def side_toe(ppm=40):
    """Viewed from the toe the face is on the right: image x = Y1 - Y."""
    Y0, Y1, Z0, Z1 = TOE_BOX
    W_, H_ = int((Y1 - Y0) * ppm), int((Z1 - Z0) * ppm)
    gold_c = Image.new("L", (W_, H_), 0)
    white_c = Image.new("L", (W_, H_), 0)
    u = lambda Ymm: Y1 - Ymm
    for txt, ya, yb, za, zb in (("PARKER 300 UNIT", 61.5, 32.7, 32.0, 34.8),
                                ("LIMITED EDITION", 61.5, 31.8, 27.6, 30.5)):
        m = text_mask(txt, F_SANS, 240, track=0.04)
        place(gold_c, m, (0, 0), (u(ya) + u(yb)) / 2, Z1 - (za + zb) / 2, w_mm=abs(ya - yb), h_mm=zb - za, ppm=ppm)
    # two-tone GR mark: colour split read off the drawing
    mark, _ = logo_masks()
    w_mm, cy = 15.0, (21.9 + 40.5) / 2
    h_mm = w_mm * mark.height / mark.width
    big = np.asarray(mark.resize((int(w_mm * ppm), int(h_mm * ppm)), Image.LANCZOS)).astype(np.float32) / 255
    a = load("head-side-right-design.jpg")
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    is_gold = (r - b > 0.16) & (r > 0.47)
    is_white = a.min(2) > 0.66
    # mark bbox on the drawing: x 577..696, y 203..342  ->  map the big mark onto it
    hh, ww = big.shape
    gx = 577 + (np.arange(ww) + 0.5) / ww * (696 - 577)
    gy = 203 + (np.arange(hh) + 0.5) / hh * (342 - 203)
    GX, GY = np.meshgrid(gx, gy)
    known = is_gold | is_white
    _, (iy, ix) = ndimage.distance_transform_edt(~known, return_indices=True)
    cls_gold = is_gold[iy, ix]
    sel = cls_gold[np.clip(GY.astype(int), 0, a.shape[0] - 1), np.clip(GX.astype(int), 0, a.shape[1] - 1)]
    cx_img = (u(29.7) + u(14.7)) / 2 * ppm
    cy_img = (Z1 - cy) * ppm
    ox, oy = int(cx_img - ww / 2), int(cy_img - hh / 2)
    for dst, m in ((gold_c, big * sel), (white_c, big * ~sel)):
        im = Image.fromarray((m * 255).astype(np.uint8))
        dst.paste(255, (ox, oy), im)
    rgba = np.zeros((H_, W_, 4), np.float32)
    ga = np.asarray(gold_c, np.float32) / 255
    wa = np.asarray(white_c, np.float32) / 255
    rgba[..., :3] = np.where(wa[..., None] > ga[..., None], np.array(WHITE) / 255, np.array(GOLD) / 255)
    rgba[..., 3] = np.maximum(ga, wa)
    Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(TEX, "side_toe.png"))


# ------------------------------------------------------------------ sole engraving
def drawing_leaf(upscale=4):
    """Left maple leaf from the bottom drawing. The brass background there is a horizontal gradient, so the
    background is estimated per column (high percentile); the engraved leaf is darker and browner.
    The red arrow is filled from its surroundings; the drawn screw circle is dropped (largest parts only)."""
    a = load("head-bottom-design.jpg")
    x0, y0, x1, y1 = 195, 238, 355, 430
    c = a[y0:y1, x0:x1]
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    red = (r > 0.5) & (g < 0.5) & (b < 0.5) & (r - g > 0.3)
    red = ndimage.binary_dilation(red, iterations=3)
    gr = g / np.maximum(r, 1e-3)                    # the engraved fill is a deeper, more orange brown
    bg = np.nanpercentile(np.where(red, np.nan, gr), 85, axis=0)[None, :]
    m = np.clip((np.nan_to_num(bg - gr) - 0.04) / 0.04, 0, 1)
    _, (iy, ix) = ndimage.distance_transform_edt(red, return_indices=True)
    m = np.where(red, m[iy, ix], m)
    lab, n = ndimage.label(m > 0.5)
    sizes = ndimage.sum(np.ones_like(m), lab, range(1, n + 1))
    keep = np.zeros_like(m, bool)
    for i in np.argsort(sizes)[::-1][:3]:                 # two leaf halves + the stem
        if sizes[i] > 60:
            keep |= lab == i + 1
    m = m * ndimage.binary_dilation(keep, iterations=1)
    big = cv2.resize(m, (m.shape[1] * upscale, m.shape[0] * upscale), interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), upscale * 0.5)
    return smooth_alpha(big, 0.4, 0.6), (x0, y0, x1, y1)


def drawing_dark_text(box, upscale=4):
    a = load("head-bottom-design.jpg")
    x0, y0, x1, y1 = box
    c = a[y0:y1, x0:x1]
    m = np.clip((0.36 - c.mean(2)) / 0.12, 0, 1)
    red = (c[..., 0] > 0.55) & (c[..., 1] < 0.45) & (c[..., 2] < 0.45)
    m[ndimage.binary_dilation(red, iterations=2)] = 0
    big = cv2.resize(m, (m.shape[1] * upscale, m.shape[0] * upscale), interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), upscale * 0.4)
    return smooth_alpha(big, 0.4, 0.6)


def sole(ppm=15):
    W_, H_ = int(HEAD_W * ppm), int(HEAD_D * ppm)
    eng = Image.new("L", (W_, H_), 0)
    blk = Image.new("L", (W_, H_), 0)
    rings = Image.new("L", (W_, H_), 0)
    org = (-HEAD_W / 2, 0)                                   # image x = X + 53, image y = Y
    mark, word = logo_masks()
    place(eng, mark, org, 0.0, 25.95, h_mm=29.6, ppm=ppm)
    place(eng, word, org, 0.0, 55.3, w_mm=45.7, ppm=ppm)
    tag = text_mask("PREMIUM MAPLE TREE", F_BLOCK, 200, track=0.08)
    place(eng, tag, org, 0.0, 63.6, w_mm=44.0, h_mm=2.3, ppm=ppm)
    d = ImageDraw.Draw(eng)
    for s in (-1, 1):
        xa, xb = sorted(((s * 23.6 + 53) * ppm, (s * 28.8 + 53) * ppm))
        d.rectangle([xa, 63.45 * ppm, xb, 63.75 * ppm], fill=255)
    # maple leaves traced from the drawing (left leaf; the right one is its mirror image)
    leaf, (lx0, ly0, lx1, ly1) = drawing_leaf()
    leaf_im = Image.fromarray((leaf * 255).astype(np.uint8))
    h_mm = (ly1 - ly0) / 6.55
    w_mm = (lx1 - lx0) / 6.55
    cx_l = ((lx0 + lx1) / 2 - 491) / 6.55
    cy_l = ((ly0 + ly1) / 2 - 170) / 6.55
    place(eng, leaf_im, org, cx_l, cy_l, w_mm=w_mm, h_mm=h_mm, ppm=ppm)
    place(eng, leaf_im.transpose(Image.FLIP_LEFT_RIGHT), org, -cx_l, cy_l, w_mm=w_mm, h_mm=h_mm, ppm=ppm)
    # DP-501 (black), traced from the drawing
    dp = drawing_dark_text((398, 610, 585, 656))
    dp_im = Image.fromarray((dp * 255).astype(np.uint8))
    place(blk, dp_im, org, ((398 + 585) / 2 - 491) / 6.55, ((610 + 656) / 2 - 170) / 6.55,
          w_mm=(585 - 398) / 6.55, h_mm=(656 - 610) / 6.55, ppm=ppm)
    # screws: present on the real sole but barely outlined (owner): a fine, faint line
    d = ImageDraw.Draw(rings)
    for X, Y in ((-41, 14), (41, 14), (-37.5, 47), (37.5, 47), (0, 84.3)):
        cx, cy, rr = (X + 53) * ppm, Y * ppm, 1.8 * ppm
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=255, width=2)     # fine line, no strong outline
    eng.save(os.path.join(TEX, "sole_engrave.png"))
    blk.save(os.path.join(TEX, "sole_black.png"))
    rings.save(os.path.join(TEX, "sole_rings.png"))


# ------------------------------------------------------------------ shaft wrap
INK = {"gold": np.array(GOLD) / 255, "grey": np.array((150, 151, 156)) / 255, "white": np.array(WHITE) / 255}


def inks(a):
    """Shaft print inks (drawing legend: white, PANTONE Cool Gray 7 C, PANTONE 4515 C). Returns alpha, class."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    L, sat = a.mean(2), a.max(2) - a.min(2)
    red = (r > 0.55) & (g < 0.4) & (b < 0.4)
    gold = np.clip((r - b - 0.10) / 0.10, 0, 1) * np.clip((r - 0.30) / 0.2, 0, 1) * \
        np.clip((g / np.maximum(r, 1e-3) - 0.55) / 0.1, 0, 1)
    neutral = np.clip(1 - (sat - 0.08) / 0.08, 0, 1)
    white = np.clip((L - 0.70) / 0.1, 0, 1) * neutral
    grey = np.clip((L - 0.36) / 0.1, 0, 1) * np.clip((0.74 - L) / 0.06, 0, 1) * neutral
    al = np.maximum.reduce([gold, white, grey]) * ~red
    cls = np.argmax(np.stack([gold, grey, white], -1), -1)       # 0 gold, 1 grey, 2 white
    return al, cls


def shaft_wrap(scale=4):
    a = load("shaft-front-closeup-design.jpg")
    band = a[378:523]                          # unrolled print: full circumference, front at the middle row
    ppm = 2.44                                 # drawing px per mm (85 mm = 207 px)
    Lpx = int(250 * ppm)
    n = min(Lpx, band.shape[1])
    full = np.zeros((band.shape[0], Lpx, 3), np.float32)
    full[:, :n] = band[:, :n]
    al = np.zeros(full.shape[:2], np.float32)
    cls = np.zeros(full.shape[:2], np.int64)
    al[:, :n], cls[:, :n] = inks(band[:, :n])
    # the aiming line runs on to the end of the 250 mm band
    if n < Lpx:
        rows = al[:, n - 30:n - 8].mean(1) > 0.45
        al[rows, n:] = al[rows, n - 12][:, None]
        cls[rows, n:] = cls[rows, n - 12][:, None]
    # back label across the seam (top and bottom rows of the unrolled print)
    al[:14] = 0
    al[-14:] = 0
    back = a[795:828, 225:446]
    bal, bcls = inks(back)
    hb = back.shape[0] // 2
    cx = int(134 * ppm) - back.shape[1] // 2
    xs = slice(cx, cx + back.shape[1])
    al[:back.shape[0] - hb, xs], cls[:back.shape[0] - hb, xs] = bal[hb:], bcls[hb:]
    al[-hb:, xs], cls[-hb:, xs] = bal[:hb], bcls[:hb]
    H2, W2 = band.shape[0] * scale, Lpx * scale
    big_al = cv2.resize(al, (W2, H2), interpolation=cv2.INTER_CUBIC)
    big_al = smooth_alpha(cv2.GaussianBlur(big_al, (0, 0), scale * 0.35), 0.3, 0.6)
    big_cls = cv2.resize(cls.astype(np.uint8), (W2, H2), interpolation=cv2.INTER_NEAREST)
    col = np.choose(big_cls[..., None], [INK["gold"][None, None], INK["grey"][None, None], INK["white"][None, None]])
    out = np.dstack([col, big_al])
    Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(TEX, "shaft_wrap.png"))


# ------------------------------------------------------------------ grip
GRIP_LEN = 280.0                            # owner's measurement
GRIP_CIRC = math.pi * 28.0
GRIP_N = 14                                 # hexagon columns round the grip (photos: ~6.6 mm apart)


def grip():
    """U = around (front at 0.5), V = along (grip end at V = 1). Measured on the grip photos (front / back / sides,
    6.48 px/mm): hexagonal pyramids 7.6 mm apart along the grip, 14 columns round it, flat sides facing the grip
    ends; smooth end bands
    (12.5 mm at the end, 8.5 mm at the shaft); a ribbed panel on the front 33.5-72 % from the end, 18 mm wide, ribs
    every 3.8 mm; recessed label panel 73.5-85.5 % with gold GRAZR; gold stars in both bands; round logo with
    an S line at 13 %."""
    W_, H_ = 1024, 4096
    v, u = np.mgrid[0:H_, 0:W_].astype(np.float32)
    from_end = v / H_ * GRIP_LEN                     # mm from the grip end (image top = grip end)
    around = (u / W_ - 0.5) * GRIP_CIRC             # mm around from the front centre
    # hexagon centres in columns along the grip, 7.6 mm apart (photos: 50 px at 6.48 px/mm), neighbouring columns
    # half a step along; GRIP_N (even) columns round the grip so the pattern closes; flat sides face the grip ends
    per = 7.6
    cw = GRIP_CIRC / GRIP_N
    sq = (per * math.sqrt(3) / 2) / cw                # around -> regular hexagon space
    best = np.full(around.shape, np.inf, np.float32)
    dx_b = np.zeros_like(around)
    dy_b = np.zeros_like(around)
    j0 = np.floor(around / cw)
    for dj in (0, 1):
        j = j0 + dj
        off = (j % 2) * 0.5
        k = np.round(from_end / per - off)
        dx = (around - j * cw) * sq
        dy = from_end - (k + off) * per
        dd = dx * dx + dy * dy
        m = dd < best
        best = np.where(m, dd, best)
        dx_b = np.where(m, dx, dx_b)
        dy_b = np.where(m, dy, dy_b)
    n1 = np.abs(dy_b)                                                  # flat sides facing the grip ends
    n2 = np.abs(dy_b * 0.5 + dx_b * math.sqrt(3) / 2)
    n3 = np.abs(dy_b * 0.5 - dx_b * math.sqrt(3) / 2)
    hexd = np.maximum(n1, np.maximum(n2, n3)) / (per / 2)
    height = np.clip(1 - hexd, 0, 1)
    panel = (np.abs(around) < 9.0) & (from_end > 0.335 * GRIP_LEN) & (from_end < 0.72 * GRIP_LEN)
    t = (from_end / (per / 2) + 0.5) % 1.0           # ribs every half step (photo: 24 px)
    rib = np.clip((0.5 - np.abs(t - 0.5)) / 0.12, 0, 1)
    rib_end = np.clip((9.0 - np.abs(around)) / 1.4, 0, 1)         # bevelled ends
    height = np.where(panel, 0.15 + 0.6 * rib * rib_end, height)
    label = (np.abs(around) < 5.2) & (from_end > 0.735 * GRIP_LEN) & (from_end < 0.855 * GRIP_LEN)
    height = np.where(label, 0.3, height)
    ends = (from_end < 12.5) | (from_end > GRIP_LEN - 8.5)
    height = np.where(ends, 0.6, height)
    # round logo with an S line at 13 %
    lc = 0.13 * GRIP_LEN
    ry, rx = from_end - lc, around
    rr = np.hypot(rx, ry)
    R0 = 5.6
    s_line = np.where(rx >= 0, np.abs(np.hypot(rx, ry + R0 / 2) - R0 / 2), np.abs(np.hypot(rx, ry - R0 / 2) - R0 / 2))
    logo = rr < R0 + 0.45
    lh = np.where(np.abs(rr - R0) < 0.4, 0.25, np.where(s_line < 0.3, 0.3, 0.55))
    height = np.where(logo, lh, height)
    Image.fromarray((np.clip(height, 0, 1) * 255).astype(np.uint8)).save(os.path.join(TEX, "grip_bump.png"))
    alb = np.full((H_, W_, 3), 0.022, np.float32)
    alb[panel] = 0.019
    alb[label] = 0.012
    img = Image.fromarray((alb * 255).astype(np.uint8))
    _, word = logo_masks()
    wm = word.rotate(-90, expand=True)                           # reads from the grip end down
    hpx = int(0.096 * H_)                                        # gold text 75-84.6 % from the end
    wm = wm.resize((max(1, int(wm.width * hpx / wm.height)), hpx), Image.LANCZOS)
    img.paste(Image.new("RGB", wm.size, GOLD), (W_ // 2 - wm.width // 2, int(0.798 * H_) - hpx // 2), wm)
    d = ImageDraw.Draw(img)
    for frac in (8.3 / GRIP_LEN, 1 - 4.5 / GRIP_LEN):
        cxp, cyp, rr_ = W_ / 2, frac * H_, 0.012 * W_ * 2.2
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            q = rr_ if k % 2 == 0 else rr_ * 0.42
            pts.append((cxp + q * math.cos(ang), cyp + q * math.sin(ang) * 1.0))
        d.polygon(pts, fill=GOLD)
    img.save(os.path.join(TEX, "grip_albedo.png"))
    # end cap: outlined GR mark + GRAZR in gold, vent hole
    cap = Image.new("RGB", (1024, 1024), (8, 8, 9))
    mark, word = logo_masks()
    m = mark.resize((int(mark.width * 470 / mark.height), 470), Image.LANCZOS)
    # outline only: mark minus an eroded copy
    ma = np.asarray(m).astype(np.float32) / 255
    er = ndimage.grey_erosion(ma, size=(15, 15))
    outline = np.clip(ma - er * 0.85, 0, 1)
    om = Image.fromarray((outline * 255).astype(np.uint8))
    cap.paste(Image.new("RGB", om.size, GOLD), (512 - om.width // 2, 175), om)
    w2 = word.resize((330, int(word.height * 330 / word.width)), Image.LANCZOS)
    cap.paste(Image.new("RGB", w2.size, GOLD), (512 - w2.width // 2, 720), w2)
    ImageDraw.Draw(cap).ellipse([497, 395, 527, 425], fill=(0, 0, 0))
    cap.save(os.path.join(TEX, "grip_cap.png"))


# ------------------------------------------------------------------ carbon weave tile
def carbon(n=1024):
    """2 x 2 cells of a plain weave (one tile = 4.3 mm, measured on the face photo: 2.15 mm tows), as the real face
    looks close up: rounded tows. carbon.png: R = 1 where the tow runs along X, G = tow height (rounded across the tow,
    dipping where it dives under the crossing tow), B = fibre streaks along each tow. carbon_shade.png: albedo shade
    seen on the photo under its top light - tows along X light with a brighter upper half and thin bright ends where
    they dive under, tows along Z dark with faint streaks. Image rows run top -> down = Z down (V = Z / 4.3)."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n * 2.0       # cell units
    cx, cy = np.floor(x), np.floor(y)
    warp = ((cx + cy) % 2) == 0                                     # tow along X on top in these cells
    fx, fy = x - cx, y - cy
    across = np.where(warp, fy, fx)                                 # 0 -> 1 across the tow (X tows: top -> bottom)
    along = np.where(warp, fx, fy)
    a = np.abs(2 * across - 1)                                      # 0 on the tow's centre line -> 1 at its sides
    dome = np.sqrt(np.clip(1 - a ** 2.2, 0, 1))                     # rounded, a little flattened on top
    e = np.abs(2 * along - 1)                                       # 0 mid-tow -> 1 where it dives under
    dive = 1 - 0.5 * np.clip((e - 0.72) / 0.28, 0, 1) ** 1.6
    height = dome * dive
    rng = np.random.default_rng(501)
    streak_x = ndimage.gaussian_filter1d(rng.random(n * 4).astype(np.float32), 1.0)[:n]
    streak_y = ndimage.gaussian_filter1d(rng.random(n * 4).astype(np.float32), 1.0)[n:2 * n]
    streak = np.where(warp, streak_y[(y / 2 * n).astype(int) % n], streak_x[(x / 2 * n).astype(int) % n])
    streak = (streak - streak.min()) / (streak.max() - streak.min())
    out = np.dstack([warp.astype(np.float32), np.clip(height, 0, 1), streak])
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(os.path.join(TEX, "carbon.png"))
    # albedo shade: the owner's face photo (140) rectified with its solved camera and folded over the weave lattice
    # (tows along X 4.33 mm, along Z 4.22 mm per 2 cells, averaged over ~250 tiles, linear light, aligned with the warp
    # mask above) -> textures/carbon_photo_tile.png (64 x 64); upsampled here, with the fibre streaks for close-ups
    tile = np.asarray(Image.open(os.path.join(TEX, "carbon_photo_tile.png")).convert("L")).astype(np.float32) / 255.0
    big = cv2.resize(np.tile(tile, (3, 3)), (3 * n, 3 * n), interpolation=cv2.INTER_CUBIC)
    big = big + 2.5 * (big - ndimage.gaussian_filter(big, 0.025 * n))      # averaging softened it: sharpen back
    big = big[n:2 * n, n:2 * n]
    big = np.clip(big / np.percentile(big, 99.5), 0, 1) ** 2.2              # and restore the photo's contrast
    shade = big * (0.88 + 0.12 * streak)
    Image.fromarray((np.clip(shade, 0, 1) * 255 + 0.5).astype(np.uint8), "L").save(os.path.join(TEX, "carbon_shade.png"))


def main():
    os.makedirs(TEX, exist_ok=True)
    top_decal()
    side_heel()
    side_toe()
    sole()
    shaft_wrap()
    grip()
    carbon()
    print("textures ->", TEX)


if __name__ == "__main__":
    main()
