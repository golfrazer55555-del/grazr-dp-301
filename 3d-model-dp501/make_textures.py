"""Textures and outlines for the GRAZR DP-501 park golf club, taken from the owner's design drawings.

  python3 3d-model-dp501/make_textures.py

Reads `grazr dp-501 parkgolf photo/*-design.jpg` (the factory artwork) and writes textures/ plus
outline.json (head outlines in mm). Drawings are cleaned so only the printed / engraved artwork
remains (construction lines, dimension arrows and the fake shading of the drawings are dropped).

Model frame (mm, same as the DP-301 model): X toe(-) -> heel(+), Y face(0) -> back(+), Z sole(0) -> up.
"""
import json
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "grazr dp-501 parkgolf photo")
TEX = os.path.join(HERE, "textures")
DP301_TEX = os.path.join(ROOT, "3d-model", "textures")
FONT_COND = os.path.join(ROOT, "3d-model", "fonts", "AsapCondensed_800ExtraBold.ttf")
FONT_SANS = os.path.join(ROOT, "3d-model", "fonts", "Montserrat_500Medium.ttf")

# ---- measured head size (KSPO test report + drawings)
HEAD_W = 106.0      # face length, toe -> heel
HEAD_D = 95.0       # face -> back of the brass nose
HEAD_H = 56.0       # test report (the drawing's 53 mm is the rule minimum)
FACE_T = 7.0        # carbon face plate ("보강재 두께 7 mm")


def load(name):
    return np.asarray(Image.open(os.path.join(SRC, name)).convert("RGB")).astype(np.float32) / 255.0


def art_alpha(a):
    """Printed artwork on black: gold (PANTONE 4515 C) and white, as a soft alpha."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    white = np.clip((mn - 0.70) / 0.20, 0, 1) * np.clip(1 - (mx - mn - 0.12) / 0.15, 0, 1)
    gold = (np.clip((r - b - 0.12) / 0.15, 0, 1) * np.clip((r - 0.30) / 0.25, 0, 1)
            * np.clip((g / np.maximum(r, 1e-3) - 0.55) / 0.12, 0, 1))      # not the red arrows
    return np.maximum(white, gold)


def rgba(a, alpha):
    """Unpremultiply-ish: push edge colours toward the artwork colour so edges don't go grey."""
    col = np.clip(a / np.maximum(alpha[..., None], 0.35), 0, 1)
    out = np.dstack([col, alpha])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def outline(mask, mm_per_px, origin_px, swap=False, flip_y=False, eps=1.2):
    """Largest contour of a mask, in mm. origin_px = pixel that maps to (0, 0)."""
    m = (mask * 255).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
    pts = []
    for x, y in c:
        u, v = (x - origin_px[0]) * mm_per_px[0], (y - origin_px[1]) * mm_per_px[1]
        if flip_y:
            v = -v
        pts.append((v, u) if swap else (u, v))
    return pts


def top_view():
    """head-top-design.jpg: face = left edge, toe = top. Returns outline (X, Y) and the top decal."""
    a = load("head-top-design.jpg")
    nonwhite = a.min(2) < 0.80
    ys, xs = np.where(nonwhite)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    sy = HEAD_D / (x1 - x0)                 # image x -> model Y
    sx = HEAD_W / (y1 - y0)                 # image y -> model X
    yc = (y0 + y1) / 2
    pts = outline(nonwhite, (sy, sx), (x0, yc), swap=True)   # -> (X, Y)
    # decal: artwork only, nothing on the brass nose (it is its own part), nothing outside the head
    al = art_alpha(a)
    al[:, int(x0 + 80.0 / sy):] = 0                     # nose starts ~81 mm from the face
    fill = np.zeros(nonwhite.shape, np.uint8)           # filled head outline, eroded so drawn edge lines go
    cs, _ = cv2.findContours(cv2.morphologyEx((nonwhite * 255).astype(np.uint8), cv2.MORPH_CLOSE,
                                              np.ones((7, 7), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(fill, [max(cs, key=cv2.contourArea)], -1, 1, -1)
    al[~cv2.erode(fill, np.ones((15, 15), np.uint8)).astype(bool)] = 0
    img = rgba(a, al).crop((x0, y0, x1 + 1, y1 + 1))
    img = img.resize((int(img.width * 2), int(img.height * 2)), Image.LANCZOS)
    img.save(os.path.join(TEX, "top_decal.png"))
    # shaft hole (black disc in the drawing): centre in mm
    dark = (a.max(2) < 0.18) & nonwhite
    blob = cv2.connectedComponentsWithStats(dark.astype(np.uint8))
    best = None
    for i in range(1, blob[0]):
        x, y, w, h, n = blob[2][i]
        if 100 < w < 220 and 0.8 < w / h < 1.25 and n > 0.6 * w * h:
            best = blob[3][i]
    hole = None
    if best is not None:
        hole = ((best[1] - yc) * sx, (best[0] - x0) * sy, None)
    return pts, hole


GOLD = (196, 160, 92)        # printed gold (PANTONE 4515 C-ish)


def colorize(mask, rgb):
    im = Image.new("RGBA", mask.size, rgb + (0,))
    im.putalpha(mask)
    return im


def side_heel():
    """Heel side: GRAZR wordmark over GOLF RAZER (gold). Layout measured on head-side-left-design.jpg."""
    _, word = masks_301()
    W = 1400
    wm = word.resize((W, int(word.height * W / word.width)), Image.LANCZOS)
    sub_ = text_mask("GOLF RAZER", FONT_SANS, 200, spacing=70)
    sub_ = sub_.resize((W, int(sub_.height * W / sub_.width)), Image.LANCZOS)
    gap = 70
    im = Image.new("L", (W + 40, wm.height + gap + sub_.height + 40), 0)
    im.paste(wm, (20, 20))
    im.paste(sub_, (20, 20 + wm.height + gap))
    img = colorize(im, GOLD)
    length = 35.2
    return img, {"y": 33.3, "z": 33.5, "len": length, "h": length * img.height / img.width}


def side_toe():
    """Toe side: PARKER 300 UNIT / LIMITED EDITION + two-tone GR mark (head-side-right-design.jpg)."""
    mark, _ = masks_301()
    H = 900
    m = mark.resize((int(mark.width * H / mark.height), H), Image.LANCZOS)
    th = 230
    lines = []
    for t in ("PARKER 300 UNIT", "LIMITED EDITION"):
        l = text_mask(t, FONT_SANS, 200, spacing=16)
        lines.append(l.resize((int(l.width * th / l.height), th), Image.LANCZOS))
    tw = max(l.width for l in lines)
    W = tw + 140 + m.width + 40
    im = Image.new("RGBA", (W, H + 40), (0, 0, 0, 0))
    ty = (H + 40) // 2 - th - 40
    for k, l in enumerate(lines):
        im.alpha_composite(colorize(l, GOLD), (20 + tw - l.width, ty + k * (th + 80)))
    mx = 20 + tw + 140
    yy, xx = np.mgrid[0:m.height, 0:m.width]
    upper_right = (xx / m.width - yy / m.height) > -0.15
    am = np.asarray(m, np.float32)
    im.alpha_composite(colorize(Image.fromarray((am * upper_right).astype(np.uint8)), (245, 245, 245)), (mx, 20))
    im.alpha_composite(colorize(Image.fromarray((am * ~upper_right).astype(np.uint8)), GOLD), (mx, 20))
    length = 48.0
    return im, {"y": 39.5, "z": 30.5, "len": length, "h": length * im.height / im.width}


def masks_301():
    mark = Image.open(os.path.join(DP301_TEX, "mark_white.png")).getchannel("A")
    word = Image.open(os.path.join(DP301_TEX, "wordmark_white.png")).getchannel("A")
    return mark, word


# Maple leaf outline: the Canadian-flag leaf path (public-domain geometry); arcs are taken as straight segments
LEAF_PATH = ("m-90 2030 45-863a95 95 0 0 0-111-98l-859 151 116-320a65 65 0 0 0-20-73l-941-762 212-99a65 65 0 0 0 "
             "34-79l-186-572 542 115a65 65 0 0 0 73-38l105-247 423 454a65 65 0 0 0 111-57l-204-1052 327 189a65 65 0 0 0 "
             "91-27l332-652 332 652a65 65 0 0 0 91 27l327-189-204 1052a65 65 0 0 0 111 57l423-454 105 247a65 65 0 0 0 73 38"
             "l542-115-186 572a65 65 0 0 0 34 79l212 99-941 762a65 65 0 0 0-20 73l116 320-859-151a95 95 0 0 0-111 98l45 863z")


def leaf_points():
    import re
    toks = re.findall(r"[a-zA-Z]|-?\d+\.?\d*", LEAF_PATH)
    pts, cmd, i, x, y = [], None, 0, 0.0, 0.0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd == "z":
                break
            continue
        if cmd == "m":
            x, y = float(toks[i]), float(toks[i + 1])
            i += 2
            cmd = "l"
        elif cmd == "l":
            x += float(toks[i])
            y += float(toks[i + 1])
            i += 2
        elif cmd == "a":
            x += float(toks[i + 5])
            y += float(toks[i + 6])
            i += 7
        pts.append((x, y))
    return pts


def maple_leaf(size, tilt=0.0):
    """Maple leaf, white on black, size px square, tilted by tilt degrees."""
    pts = leaf_points()
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    k = 0.9 * size / max(max(xs) - min(xs), max(ys) - min(ys))
    t = math.radians(tilt)
    out = [(size / 2 + (x - cx) * k * math.cos(t) - (y - cy) * k * math.sin(t),
            size / 2 + (x - cx) * k * math.sin(t) + (y - cy) * k * math.cos(t)) for x, y in pts]
    im = Image.new("L", (size, size), 0)
    ImageDraw.Draw(im).polygon(out, fill=255)
    return im


def text_mask(txt, path, px, spacing=0):
    f = ImageFont.truetype(path, px)
    w = int(f.getlength(txt) + spacing * len(txt) + 20)
    im = Image.new("L", (w, int(px * 1.5)), 0)
    d = ImageDraw.Draw(im)
    x = 10
    for ch in txt:
        d.text((x, 0), ch, font=f, fill=255)
        x += f.getlength(ch) + spacing
    return im.crop(im.getbbox())


def paste_fit(dst, mask, cx, cy, h=None, w=None):
    if h is not None:
        mask = mask.resize((max(1, int(mask.width * h / mask.height)), int(h)), Image.LANCZOS)
    else:
        mask = mask.resize((int(w), max(1, int(mask.height * w / mask.width))), Image.LANCZOS)
    dst.paste(255, (int(cx - mask.width / 2), int(cy - mask.height / 2)), mask)


def sole():
    """Brass sole engraving (owner drawing head-bottom-design.jpg, laid out in mm).

    sole_engrave.png: sand-blasted engraving (GR mark, maple leaves, GRAZR, PREMIUM MAPLE TREE)
    sole_black.png:   black-filled DP-501
    Texture frame: 10 px/mm, x = model X (toe -> heel) + W/2, y = model Y (face -> back)."""
    ppm = 10
    W, H = int(HEAD_W * ppm), int(HEAD_D * ppm)
    eng = Image.new("L", (W, H), 0)
    blk = Image.new("L", (W, H), 0)
    mark, word = masks_301()
    X = lambda mm: W / 2 + mm * ppm
    Y = lambda mm: mm * ppm
    # positions measured on the drawing (106 mm = 690 px, face edge at y=170)
    paste_fit(eng, mark, X(0), Y(26), h=30 * ppm)
    for sx in (-33.5, 33.5):
        leaf = maple_leaf(26 * ppm, tilt=-20 if sx < 0 else 20)
        paste_fit(eng, leaf, X(sx), Y(25), h=26 * ppm)
    paste_fit(eng, word, X(0), Y(55), w=45 * ppm)
    tag = text_mask("PREMIUM MAPLE TREE", FONT_COND, 60, spacing=6)
    paste_fit(eng, tag, X(0), Y(63), h=2.6 * ppm)
    d = ImageDraw.Draw(eng)
    for sgn in (-1, 1):                           # the little rules either side of the tag
        d.line([(X(sgn * 19), Y(63)), (X(sgn * 27.5), Y(63))], fill=255, width=3)
    paste_fit(blk, text_mask("DP-501", FONT_COND, 120, spacing=10), X(0), Y(70), h=4.8 * ppm)
    # engraving rim: a thin bright outline around each engraved shape (cut edge)
    eng.save(os.path.join(TEX, "sole_engrave.png"))
    blk.save(os.path.join(TEX, "sole_black.png"))


def shaft():
    """Shaft wrap from shaft-front-closeup-design.jpg (the 250 mm graphic band, unrolled around the shaft).

    U (image x) = along the shaft, butt-side end of the band -> tip side; V (image y) = around, front at 0.5."""
    a = load("shaft-front-closeup-design.jpg")
    band = a[378:523, :, :]                       # unrolled front band (full circumference)
    # the closeup shows 220 of the 250 mm: GR mark ~12 mm in, X centre ~134 mm in (2.48 px/mm)
    ppm = 2.48
    full = np.zeros((band.shape[0], int(250 * ppm), 3), np.float32) + band[:, -1:, :] * 0
    full[:, :band.shape[1]] = band
    # continue the aiming line to the end of the band
    line_rows = np.where(art_alpha(band[:, -40:-20]).mean(1) > 0.5)[0]
    for r in line_rows:
        full[r, band.shape[1]:] = band[r, -30]
    al = art_alpha(full)
    # seam at the back: clear the half-cut tags, put the back label (85 mm wide) across the seam
    al[:12] = 0
    al[-12:] = 0
    back = load("shaft-front-closeup-design.jpg")[795:828, 225:446]
    bal = art_alpha(back)
    hb = back.shape[0] // 2
    cx = int(134 * ppm) - back.shape[1] // 2
    lo, hi = back[hb:], back[:hb]                 # lower half of the label at the top edge, upper half at the bottom
    xs = slice(cx, cx + back.shape[1])
    full[:lo.shape[0], xs], al[:lo.shape[0], xs] = lo, bal[hb:]
    full[-hb:, xs], al[-hb:, xs] = hi, bal[:hb]
    img = rgba(full, al)
    img = img.resize((img.width * 4, img.height * 4), Image.LANCZOS)
    img.save(os.path.join(TEX, "shaft_wrap.png"))


def carbon():
    """Plain-weave carbon (the face plate): 3 mm tows, 512 px = 12 mm tile."""
    n, tow = 512, 128
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cx, cy = (x // tow).astype(int), (y // tow).astype(int)
    over = (cx + cy) % 2 == 0                          # warp over weft
    u = (x % tow) / tow
    v = (y % tow) / tow
    # each tow is a rounded bundle of fibres: brightness peaks across the tow, fibre streaks along it
    across = np.where(over, u, v)
    along = np.where(over, v, u)
    hump = np.maximum(np.sin(np.pi * np.clip(across * 1.06 - 0.03, 0, 1)), 0) ** 0.6
    rng = np.random.default_rng(501)
    streak_x = rng.random(n).astype(np.float32)
    fib = np.where(over, streak_x[x.astype(int) % n], streak_x[y.astype(int) % n])
    shade = 0.18 + 0.55 * hump * (0.85 + 0.15 * fib)
    shade *= np.where(over, 1.0, 0.72)
    alb = np.clip(shade * 0.10 + 0.012, 0, 1)
    Image.fromarray((np.dstack([alb * 0.95, alb * 0.98, alb * 1.05]) * 255).clip(0, 255).astype(np.uint8)).save(
        os.path.join(TEX, "carbon_albedo.png"))
    bump = 0.5 + 0.5 * hump * np.where(over, 1.0, 0.85) - 0.05 * np.sin(np.pi * along) ** 8
    Image.fromarray((bump * 255).clip(0, 255).astype(np.uint8)).save(os.path.join(TEX, "carbon_bump.png"))
    # anisotropy direction (along the fibres): R/G = tangent
    tan = np.where(over[..., None], np.array([0.5, 1.0, 0.5]), np.array([1.0, 0.5, 0.5]))
    Image.fromarray((tan * 255).astype(np.uint8)).save(os.path.join(TEX, "carbon_tangent.png"))


GRIP_LEN = 350.0
GRIP_R0, GRIP_R1 = 14.0, 11.5            # butt / lower end radius (mm)


def grip():
    """Black rubber grip with a pyramid (diamond) texture, GRAZR in gold near the lower third,
    a ribbed reminder panel on the front, and a GR cap."""
    W, H = 512, 2048                      # U = around (front at 0.5), V = along (butt at 0)
    v, u = np.mgrid[0:H, 0:W].astype(np.float32)
    mm_v = v / H * GRIP_LEN
    mm_u = u / W * (2 * math.pi * 12.8)
    p = 5.0                               # pyramid pitch (mm)
    du = np.abs(((mm_u / p) % 1) - 0.5)
    dv = np.abs(((mm_v / p + 0.5 * ((mm_u // p) % 2)) % 1) - 0.5)
    pyr = 1 - 2 * np.maximum(du, dv * 0.9)
    panel = (np.abs(u / W - 0.5) < 0.055) & (mm_v > 70) & (mm_v < 205)
    ribs = 0.5 + 0.5 * np.cos(mm_v * 2 * math.pi / 1.6)
    bump = np.where(panel, 0.35 + 0.25 * ribs, 0.25 + 0.6 * pyr)
    ends = (mm_v < 4) | (mm_v > GRIP_LEN - 6)
    bump = np.where(ends, 0.5, bump)
    Image.fromarray((bump * 255).clip(0, 255).astype(np.uint8)).save(os.path.join(TEX, "grip_bump.png"))
    alb = np.full((H, W, 3), 0.018, np.float32)
    alb[panel] = 0.024
    img = Image.fromarray((alb * 255).astype(np.uint8))
    _, word = masks_301()
    # GRAZR along the grip (reads butt -> tip), gold, on the front a little below the panel
    wm = word.rotate(-90, expand=True)
    paste_v = int(250 / GRIP_LEN * H)
    hpx = int(46 / GRIP_LEN * H)
    wm = wm.resize((max(1, int(wm.width * hpx / wm.height)), hpx), Image.LANCZOS)
    gold = Image.new("RGB", wm.size, (178, 140, 72))
    img.paste(gold, (W // 2 - wm.width // 2, paste_v - hpx // 2), wm)
    d = ImageDraw.Draw(img)
    for vv in (12, GRIP_LEN - 14):                # little stars at the ends
        cyp = vv / GRIP_LEN * H
        r = 9
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.42
            pts.append((W / 2 + rr * math.cos(ang), cyp + rr * math.sin(ang)))
        d.polygon(pts, fill=(178, 140, 72))
    img.save(os.path.join(TEX, "grip_albedo.png"))
    # cap: GR mark + GRAZR in gold on black rubber
    cap = Image.new("RGB", (512, 512), (6, 6, 6))
    mark, word = masks_301()
    m = mark.resize((int(mark.width * 230 / mark.height), 230), Image.LANCZOS)
    goldc = (178, 140, 72)
    cap.paste(Image.new("RGB", m.size, goldc), (256 - m.width // 2, 110), m)
    w2 = word.resize((200, int(word.height * 200 / word.width)), Image.LANCZOS)
    cap.paste(Image.new("RGB", w2.size, goldc), (256 - w2.width // 2, 360), w2)
    cap.save(os.path.join(TEX, "grip_cap.png"))


def main():
    os.makedirs(TEX, exist_ok=True)
    top, hole = top_view()
    heel_img, heel_place = side_heel()
    toe_img, toe_place = side_toe()
    heel_img.save(os.path.join(TEX, "side_heel.png"))
    toe_img.save(os.path.join(TEX, "side_toe.png"))
    sole()
    shaft()
    carbon()
    grip()
    out = {"top": top, "shaft_hole": hole[:2] if hole else None,
           "heel_text": heel_place, "toe_text": toe_place,
           "head": {"w": HEAD_W, "d": HEAD_D, "h": HEAD_H, "face_t": FACE_T}}
    with open(os.path.join(HERE, "outline.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print("shaft hole (X, Y mm):", out["shaft_hole"])
    print("heel text:", heel_place, "\ntoe text:", toe_place)
    print("top outline pts:", len(top))


if __name__ == "__main__":
    main()
