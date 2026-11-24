"""Thumbnails for the GRAZR DP-501 film (same look as the DP-301 ones in video3d/shorts.py).

  python3 video501/thumbs.py --frames video501/frames --out video501/out/GRAZR_DP-501_film_thumb.jpg
  python3 video501/thumbs.py --frames video501/frames_v --vertical --out video501/out/GRAZR_DP-501_film_9x16_cover.jpg

The picture is a rendered frame (no copy burned in); the headline, sub line and logo are drawn here.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compose as C  # noqa: E402

F_KR_B = os.path.join(HERE, "fonts", "Pretendard-Regular.otf")
F_EN_M = os.path.join(HERE, "fonts", "Montserrat_500Medium.ttf")
HEAD = "300개 한정 프리미엄 파크골프채"
HEAD_V = ("300개 한정", "프리미엄 파크골프채")
SUB = "GRAZR DP-501  ·  PREMIUM MAPLE TREE"
SUB_V = "PREMIUM MAPLE TREE"
FRAME = 156                      # reveal: carbon face, PARKER 300 UNIT, the head clear of the headline
GOLD = (222, 190, 120)


def logo(h):
    lg = Image.open(C.LOGO).convert("RGBA")
    lg = lg.crop(lg.getchannel("A").getbbox())
    return lg.resize((int(lg.width * h / lg.height), h), Image.LANCZOS)


def film_thumb(frames, out, n=FRAME):
    img = np.asarray(Image.open(C.frame_path(frames, n)).convert("RGB"), np.float32) / 255.0
    H, W = img.shape[:2]
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    img = img * (1.0 - 0.8 * np.clip((yy - 0.58) / 0.32, 0, 1) ** 1.3)
    im = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).resize((1920, 1080), Image.LANCZOS)
    lg = logo(150)
    im.paste(lg, (70, 60), lg)
    d = ImageDraw.Draw(im)
    f_kr = ImageFont.truetype(F_KR_B, 100)
    w = d.textlength(HEAD, font=f_kr)
    d.text(((1920 - w) / 2, 850), HEAD, font=f_kr, fill=(245, 245, 245))
    sub = C.tracked(SUB, ImageFont.truetype(F_EN_M, 36), 9)
    im.paste(GOLD, ((1920 - sub.width) // 2, 790), sub)
    im.resize((1280, 720), Image.LANCZOS).save(out, quality=92)
    print(out)


def film_thumb_v(frames, out, n=FRAME):
    """9:16 Reels / Shorts cover; text kept inside the centre 3:4 the profile grid shows."""
    W_, H_ = 1080, 1920
    img = np.asarray(Image.open(C.frame_path(frames, n)).convert("RGB"), np.float32) / 255.0
    yy = np.linspace(0, 1, H_, dtype=np.float32)[:, None, None]
    img = img * (1.0 - 0.8 * np.exp(-((yy - 0.68) / 0.12) ** 2))
    im = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    lg = logo(120)
    im.paste(lg, ((W_ - lg.width) // 2, int(H_ * 0.15)), lg)
    d = ImageDraw.Draw(im)
    f_kr = ImageFont.truetype(F_KR_B, 88)
    sub = C.tracked(SUB_V, ImageFont.truetype(F_EN_M, 34), 10)
    y = int(H_ * 0.64)
    im.paste(GOLD, ((W_ - sub.width) // 2, y - 60), sub)
    for line in HEAD_V:
        w = d.textlength(line, font=f_kr)
        d.text(((W_ - w) / 2, y), line, font=f_kr, fill=(245, 245, 245))
        y += 112
    im.save(out, quality=92)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frame", type=int, default=FRAME)
    ap.add_argument("--vertical", action="store_true")
    a = ap.parse_args()
    (film_thumb_v if a.vertical else film_thumb)(a.frames, a.out, a.frame)
