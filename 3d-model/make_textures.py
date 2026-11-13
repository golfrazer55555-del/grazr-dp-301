"""Texture generator for the GRAZR DP-301 model (PIL only, no Blender needed).

Builds, from `grazr dp-301 putter photo/logo.png` and system fonts:
  textures/mark_white.png       GR hex mark, white on transparent (head / shaft decals)
  textures/wordmark_white.png   GRAZR wordmark, white on transparent
  textures/grip_albedo.png      unrolled grip print (u = around, v = along, butt at top)
  textures/grip_bump.png        grip surface texture (raised cross/dash pattern)
  textures/grip_cap.png         butt-end cap with embossed GR mark
  textures/shaft_decal.png      unrolled shaft print below the grip (GR mark + DP-301 label)

Layouts are drawn in millimetres (see the *_PX constants) so they match the
geometry built in build_dp301.py.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
SRC = os.path.join(HERE, "..", "grazr dp-301 putter photo", "logo.png")
FONT_DIR = "/usr/share/fonts/opentype/inter"


def font(weight, px):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{weight}.otf"), int(px))


# ------------------------------------------------------------------ logo masks
def _sharpen(mask):
    lut = [0 if v < 90 else 255 if v > 170 else int((v - 90) * 255 / 80) for v in range(256)]
    return mask.point(lut)


def logo_masks():
    a = np.array(Image.open(SRC).convert("RGBA"))[..., 3]

    def crop(r0, r1):
        sub = a[r0:r1]
        rows = np.where(sub.max(1) > 8)[0]
        cols = np.where(sub.max(0) > 8)[0]
        return Image.fromarray(sub[rows.min():rows.max() + 1, cols.min():cols.max() + 1])

    return crop(100, 418), crop(418, 520)      # GR mark, GRAZR wordmark (alpha, mode L)


MARK, WORD = logo_masks()
MARK_ASPECT = MARK.width / MARK.height        # w / h
WORD_ASPECT = WORD.width / WORD.height


def mask_sized(mask, w, h):
    return _sharpen(mask.resize((max(1, int(round(w))), max(1, int(round(h)))), Image.LANCZOS))


def paint(base, mask, xy, color):
    """Composite a flat colour through `mask` onto RGB image `base` at top-left xy."""
    layer = Image.new("RGB", mask.size, color)
    base.paste(layer, (int(round(xy[0])), int(round(xy[1]))), mask)


def white_png(mask, path, height_px):
    m = mask_sized(mask, height_px * mask.width / mask.height, height_px)
    img = Image.new("RGBA", m.size, (255, 255, 255, 0))
    img.putalpha(m)
    img.save(path)


def text_mask(txt, fnt, pad=4):
    l, t, r, b = fnt.getbbox(txt)
    m = Image.new("L", (r - l + 2 * pad, b - t + 2 * pad), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), txt, font=fnt, fill=255)
    return m


# ------------------------------------------------------------------ grip
GRIP_LEN = 270.0
GRIP_R = 14.5             # round section radius (29 mm)
GRIP_FLAT_HALF = 10.0     # 20 mm flat
GRIP_PX = 12              # px per mm


def grip_perimeter(r=GRIP_R, half=GRIP_FLAT_HALF):
    a = math.asin(half / r)
    return r * (2 * math.pi - 2 * a) + 2 * half


def make_grip():
    P = grip_perimeter()
    W, H = int(round(P * GRIP_PX)), int(round(GRIP_LEN * GRIP_PX))
    X = lambda s: W / 2 + s * GRIP_PX
    Y = lambda t: t * GRIP_PX

    BLACK, GREY, MARKC, SLIVER, TXT = (10, 10, 11), (112, 113, 114), (98, 99, 101), (168, 169, 170), (96, 97, 98)
    img = Image.new("RGB", (W, H), BLACK)
    smooth = Image.new("L", (W, H), 0)          # areas without the bump pattern
    d = ImageDraw.Draw(img)
    ds = ImageDraw.Draw(smooth)

    # big GR hex mark wrapping the upper grip (pointy top/bottom, upright)
    mh, mw = 102.0, 102.0 * MARK_ASPECT
    m = mask_sized(MARK, mw * GRIP_PX, mh * GRIP_PX)
    top = 8.0
    paint(img, m, (X(-mw / 2), Y(top)), MARKC)
    smooth.paste(255, (int(X(-mw / 2)), int(Y(top))), m)
    hex_bottom = top + mh
    slope = (mh / 4) / (mw / 2)                 # lower hex edge rise per mm around

    # grey front panel under the hex (V-shaped top), black band at the bottom
    gap = 4.5
    pw = 14.0
    panel = [(X(-pw), Y(hex_bottom + gap - pw * slope)), (X(0), Y(hex_bottom + gap)),
             (X(pw), Y(hex_bottom + gap - pw * slope)), (X(pw), Y(258)), (X(-pw), Y(258))]
    d.polygon(panel, fill=GREY)

    # GRAZR wordmark down the panel (reads top -> bottom)
    wl, wh = 118.0, 118.0 / WORD_ASPECT
    wm = mask_sized(WORD, wl * GRIP_PX, wh * GRIP_PX).rotate(-90, expand=True)
    y0 = 128.0
    paint(img, wm, (X(-wh / 2), Y(y0)), BLACK)
    smooth.paste(255, (int(X(-wh / 2)), int(Y(y0))), wm)

    # tapering slivers on both sides of the panel
    for sg in (-1, 1):
        s_in, s_out = 15.5, 28.5
        poly = [(X(sg * s_in), Y(hex_bottom + gap - s_in * slope)),
                (X(sg * s_out), Y(hex_bottom + gap - s_out * slope)),
                (X(sg * 16.2), Y(238))]
        d.polygon(poly, fill=SLIVER)
        ds.polygon(poly, fill=255)

    # side texts, letter tops toward the front panel
    fnt = font("SemiBold", 3.6 * GRIP_PX / 0.73)
    for txt, sg, tc, rot in (("NON-SLIP", 1, 190.0, 90), ("STANDARD 2.0", -1, 182.0, -90)):
        tm = text_mask(txt, fnt).rotate(rot, expand=True)
        paint(img, tm, (X(sg * 24.5) - tm.width / 2, Y(tc) - tm.height / 2), TXT)

    img.save(os.path.join(TEX, "grip_albedo.png"))

    # bump: staggered "dagger" crosses everywhere except the smooth print areas
    bump = Image.new("L", (W, H), 0)
    db = ImageDraw.Draw(bump)
    sx, ty = 3.3, 5.6
    row = 0
    t = 1.0
    while t < GRIP_LEN:
        off = (sx / 2) if row % 2 else 0.0
        s = -P / 2 + off
        while s < P / 2:
            cx, cy = X(s), Y(t)
            db.rectangle((cx - 0.22 * GRIP_PX, cy - 1.5 * GRIP_PX, cx + 0.22 * GRIP_PX, cy + 1.5 * GRIP_PX), fill=255)
            db.rectangle((cx - 0.7 * GRIP_PX, cy - 0.75 * GRIP_PX, cx + 0.7 * GRIP_PX, cy - 0.35 * GRIP_PX), fill=255)
            s += sx
        t += ty / 2
        row += 1
    # mould seam at the back
    db.line((0, 0, 0, H), fill=160, width=3)
    db.line((W - 1, 0, W - 1, H), fill=160, width=3)
    bump = Image.composite(Image.new("L", (W, H), 0), bump, smooth)
    bump.filter(ImageFilter.GaussianBlur(1.2)).save(os.path.join(TEX, "grip_bump.png"))

    # butt cap: dark rubber with the GR mark embossed, vent hole in the middle
    C = 512
    cap = Image.new("RGB", (C, C), (24, 24, 25))
    cm = mask_sized(MARK, 0.62 * C * MARK_ASPECT, 0.62 * C)
    edges = cm.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    paint(cap, edges, ((C - cm.width) / 2, (C - cm.height) / 2), (92, 92, 94))
    hole = C / 29.0 * 1.3
    ImageDraw.Draw(cap).ellipse((C / 2 - hole, C / 2 - hole, C / 2 + hole, C / 2 + hole), fill=(0, 0, 0))
    cap.save(os.path.join(TEX, "grip_cap.png"))
    return P


# ------------------------------------------------------------------ shaft
SHAFT_DECAL_LEN = 260.0   # mm of shaft below the grip covered by the decal sleeve
SHAFT_PX = 16


def make_shaft(radius_at):
    """radius_at(v) -> shaft radius (mm) at v mm below the grip."""
    W, H = 640, int(SHAFT_DECAL_LEN * SHAFT_PX)
    img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    alpha = Image.new("L", (W, H), 0)

    def around_px(v):            # px per mm around the shaft at depth v
        return W / (2 * math.pi * radius_at(v))

    # GR mark 71 mm below the grip, upright (point toward the grip)
    v_mark, mh = 71.0, 21.0
    mw = mh * MARK_ASPECT
    m = mask_sized(MARK, mw * around_px(v_mark), mh * SHAFT_PX)
    alpha.paste(255, (int(W / 2 - m.width / 2), int((v_mark - mh / 2) * SHAFT_PX)), m)

    # DP-301 label, reads toward the grip; composed horizontally then rotated
    big = font("ExtraBoldItalic", 4.6 * SHAFT_PX / 0.73)
    small = font("Medium", 1.45 * SHAFT_PX / 0.73)
    parts = []
    parts.append(text_mask("DP-301", big))
    l1, l2 = text_mask("HIGH PERFORMANCE GRAPHITE", small), text_mask("DESIGNED BY U.S.A.", small)
    block = Image.new("L", (max(l1.width, l2.width), l1.height + l2.height + 6), 0)
    block.paste(l1, (0, 0))
    block.paste(l2, (0, l1.height + 6))
    parts.append(block)
    # "S" flex emblem: rounded box outline with S inside
    eh = int(4.2 * SHAFT_PX)
    emb = Image.new("L", (int(eh * 1.25), eh), 0)
    de = ImageDraw.Draw(emb)
    de.rounded_rectangle((2, 2, emb.width - 3, emb.height - 3), radius=eh // 4, outline=255, width=max(3, eh // 12))
    sm = text_mask("S", font("ExtraBold", eh * 0.62 / 0.73), pad=0)
    emb.paste(sm, ((emb.width - sm.width) // 2, (emb.height - sm.height) // 2), sm)
    parts.append(emb)
    f1, f2 = text_mask("PUTTER", small), text_mask("FLEX", small)
    flex = Image.new("L", (max(f1.width, f2.width), f1.height + f2.height + 6), 0)
    flex.paste(f1, (0, 0))
    flex.paste(f2, (0, f1.height + 6))
    parts.append(flex)

    gapx = int(3.0 * SHAFT_PX)
    Lw = sum(p.width for p in parts) + gapx * (len(parts) - 1)
    Lh = max(p.height for p in parts)
    label = Image.new("L", (Lw, Lh), 0)
    x = 0
    for p in parts:
        label.paste(p, (x, (Lh - p.height) // 2))
        x += p.width + gapx
    v_label = 175.0                               # centre of the label below the grip
    rot = label.rotate(90, expand=True)           # reads bottom -> top (toward the grip)
    rot = rot.resize((max(1, int(rot.width * around_px(v_label) / SHAFT_PX)), rot.height), Image.LANCZOS)
    alpha.paste(255, (int(W / 2 - rot.width / 2), int(v_label * SHAFT_PX - rot.height / 2)), rot)

    img.putalpha(alpha)
    img.save(os.path.join(TEX, "shaft_decal.png"))


def make_all(shaft_radius_at):
    os.makedirs(TEX, exist_ok=True)
    white_png(MARK, os.path.join(TEX, "mark_white.png"), 1024)
    white_png(WORD, os.path.join(TEX, "wordmark_white.png"), 256)
    P = make_grip()
    make_shaft(shaft_radius_at)
    return P


if __name__ == "__main__":
    make_all(lambda v: 5.8 - 0.0024 * v)
    print("textures written to", TEX)
