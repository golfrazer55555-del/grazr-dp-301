"""GRAZR channel images: profile (800x800) and banner (2560x1440, YouTube safe area 1546x423).

  python3 video3d/brand_assets.py --frames video3d/frames --out video3d/out/brand
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageFont

import compose as C

F_EN = os.path.join(C.HERE, "fonts", "Montserrat_400Regular.ttf")


def logo_parts():
    lg = Image.open(C.LOGO).convert("RGBA")
    a = np.asarray(lg)[..., 3]
    rows = np.where(a.max(1) > 20)[0]
    split = rows[0] + np.argmax(a[rows[0]:].max(1)[1:] <= 20) + 1   # first empty row under the mark
    mark = lg.crop((0, 0, lg.width, split))
    word = lg.crop((0, split, lg.width, lg.height))
    return mark.crop(mark.getbbox()), word.crop(word.getbbox())


def fit(im, h):
    return im.resize((int(round(im.width * h / im.height)), h), Image.LANCZOS)


def radial(W, H, cx, cy, rx, ry, level):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    return level * np.clip(1 - r, 0, 1) ** 2


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def profile(out):
    S = 800
    bg = np.full((S, S, 3), 0.035, np.float32) + radial(S, S, S / 2, S * 0.46, S * 0.55, S * 0.55, 0.10)[..., None]
    im = to_img(bg).convert("RGBA")
    mark, _ = logo_parts()
    m = fit(mark, int(S * 0.50))
    im.alpha_composite(m, ((S - m.width) // 2, (S - m.height) // 2))
    im.convert("RGB").save(os.path.join(out, "GRAZR_profile_800.png"))


def banner(frames, out, n):
    W, H = 2560, 1440
    src = Image.open(C.frame_path(frames, n)).convert("RGB").resize((W, H), Image.LANCZOS)
    a = np.asarray(src, np.float32) / 255.0 * 0.42
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # keep the milled pattern at the sides, calm black band behind the logo in the safe area
    band = np.exp(-((xx - W / 2) / 900) ** 2) * np.exp(-((yy - H / 2) / 420) ** 2)
    a = a * (1 - 0.85 * band)[..., None]
    edge = np.clip(np.abs(yy - H / 2) / (H / 2), 0, 1) ** 2      # fade top/bottom for TV
    a = a * (1 - 0.6 * edge)[..., None]
    im = to_img(a).convert("RGBA")
    mark, word = logo_parts()
    m, w = fit(mark, 240), fit(word, 84)
    f = ImageFont.truetype(F_EN, 30)
    tag = C.tracked("PRECISION YOU CAN SEE", f, 12)
    gap = 56
    block = m.width + gap + max(w.width, tag.width)
    x0 = (W - block) // 2
    im.alpha_composite(m, (x0, H // 2 - m.height // 2))
    tx = x0 + m.width + gap
    th = w.height + 38 + tag.height
    ty = H // 2 - th // 2
    im.alpha_composite(w, (tx, ty))
    tagc = Image.new("RGBA", tag.size, (200, 200, 200, 0))
    tagc.putalpha(tag.point(lambda v: int(v * 0.85)))
    im.alpha_composite(tagc, (tx + 4, ty + w.height + 38))
    im.convert("RGB").save(os.path.join(out, "GRAZR_banner_2560x1440.png"))
    if not os.environ.get("BRAND_GUIDE"):
        return
    # guide copy with the YouTube safe areas drawn (BRAND_GUIDE=1), for checking only
    from PIL import ImageDraw
    g = im.convert("RGB").copy()
    d = ImageDraw.Draw(g)
    for bw, bh, col in ((1546, 423, (255, 80, 80)), (2560, 423, (80, 160, 255))):
        d.rectangle(((W - bw) // 2, (H - bh) // 2, (W + bw) // 2, (H + bh) // 2), outline=col, width=4)
    g.save(os.path.join(out, "_banner_safe_area_check.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frame", type=int, default=200)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    profile(a.out)
    banner(a.frames, a.out, a.frame)


if __name__ == "__main__":
    main()


def kakao_and_instagram(frames, out):
    """KakaoTalk channel profile/cover and Instagram profile + highlight covers."""
    from PIL import ImageDraw
    F_KR = os.path.join(C.HERE, "fonts", "Pretendard-Regular.otf")
    mark, word = logo_parts()
    # profile 640 (Kakao) / 1080 (Instagram): the GR mark, reads as a circle
    for S, name in ((640, "kakao_profile_640.png"), (1080, "instagram_profile_1080.png")):
        bg = np.full((S, S, 3), 0.035, np.float32) + radial(S, S, S / 2, S * 0.46, S * 0.55, S * 0.55, 0.10)[..., None]
        im = to_img(bg).convert("RGBA")
        m = fit(mark, int(S * 0.48))
        im.alpha_composite(m, ((S - m.width) // 2, (S - m.height) // 2))
        im.convert("RGB").save(os.path.join(out, name))
    # Kakao channel cover: square 1600, content in the middle band so a wide crop keeps it
    S = 1600
    src = Image.open(C.frame_path(frames, 230)).convert("RGB")
    src = src.resize((int(src.width * S / src.height), S), Image.LANCZOS)
    x0 = (src.width - S) // 2
    a = np.asarray(src.crop((x0, 0, x0 + S, S)), np.float32) / 255.0 * 0.45
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    band = np.exp(-((yy - S / 2) / 330) ** 2) * np.exp(-((xx - S / 2) / 700) ** 2)
    a = a * (1 - 0.85 * band)[..., None]
    im = to_img(a).convert("RGBA")
    m, w = fit(mark, 190), fit(word, 70)
    f = ImageFont.truetype(F_EN, 26)
    tag = C.tracked("PRECISION YOU CAN SEE", f, 11)
    gap = 48
    bw = m.width + gap + max(w.width, tag.width)
    x = (S - bw) // 2
    im.alpha_composite(m, (x, S // 2 - m.height // 2))
    tx, th = x + m.width + gap, w.height + 30 + tag.height
    ty = S // 2 - th // 2
    im.alpha_composite(w, (tx, ty))
    tc = Image.new("RGBA", tag.size, (200, 200, 200, 0))
    tc.putalpha(tag.point(lambda v: int(v * 0.85)))
    im.alpha_composite(tc, (tx + 4, ty + w.height + 30))
    im.convert("RGB").save(os.path.join(out, "kakao_cover_1600.png"))
    # Instagram highlight covers (1080x1920, content inside the centre circle)
    f_kr = ImageFont.truetype(F_KR, 120)
    for key, label in (("about", None), ("features", "기능"), ("review", "후기"), ("buy", "구매")):
        W, H = 1080, 1920
        bg = np.full((H, W, 3), 0.03, np.float32) + radial(W, H, W / 2, H / 2, 520, 520, 0.12)[..., None]
        im = to_img(bg).convert("RGBA")
        d = ImageDraw.Draw(im)
        d.ellipse((W / 2 - 400, H / 2 - 400, W / 2 + 400, H / 2 + 400), outline=(120, 120, 124, 255), width=6)
        if label is None:
            m = fit(mark, 360)
            im.alpha_composite(m, ((W - m.width) // 2, (H - m.height) // 2))
        else:
            tw = d.textlength(label, font=f_kr)
            d.text(((W - tw) / 2, H / 2 - 82), label, font=f_kr, fill=(235, 235, 238, 255))
        im.convert("RGB").save(os.path.join(out, f"instagram_highlight_{key}.png"))
