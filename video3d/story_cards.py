"""9:16 Instagram story cards (purchase info) for the GRAZR highlights.

  python3 video3d/story_cards.py --out video3d/out/brand
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import compose as C

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
W, H = 1080, 1920
KR = os.path.join(HERE, "fonts", "Pretendard-Regular.otf")
KR_L = os.path.join(HERE, "fonts", "Pretendard-Light.otf")
EN = os.path.join(HERE, "fonts", "Montserrat_500Medium.ttf")
FRAMES_V = os.path.join(HERE, "frames_v")   # 9:16 film frames (scene.py --vertical)


def soft_mask(w, h, edge_x, edge_y):
    x = np.minimum(np.arange(w), np.arange(w)[::-1])[None, :] / edge_x
    y = np.minimum(np.arange(h), np.arange(h)[::-1])[:, None] / edge_y
    m = np.clip(np.minimum(x, y), 0, 1) ** 1.5
    return Image.fromarray((m * 255).astype(np.uint8))


def centered(d, y, text, font, fill):
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, font=font, fill=fill)


def buy_card(out):
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    lg = Image.open(C.LOGO).convert("RGBA")
    lg = lg.crop(lg.getchannel("A").getbbox())
    lg = lg.resize((int(lg.width * 96 / lg.height), 96), Image.LANCZOS)
    im.paste(lg, ((W - lg.width) // 2, 200), lg)

    # hero frame from the vertical film: head + shaft on the black studio floor
    fr = Image.open(C.frame_path(FRAMES_V, 150)).convert("RGB").crop((0, 260, W, 1300))
    im.paste(fr, (0, 300), soft_mask(W, fr.height, 1, 260))
    f = ImageFont.truetype(KR, 32)
    centered(d, 1330, "33인치 실버  /  34인치 블랙 샤프트 · 같은 가격", f, (200, 200, 204))

    sub = C.tracked("GRAZR DP-301", ImageFont.truetype(EN, 30), 10)
    im.paste((190, 190, 194), ((W - sub.width) // 2, 1405), sub)
    centered(d, 1450, "385,000원", ImageFont.truetype(KR, 92), (245, 245, 247))
    f = ImageFont.truetype(KR_L, 34)
    y = 1585
    for line in ("무료배송 · 로젠택배 · 결제 후 1일 이내 발송",
                 "구성: 퍼터 + 전용 헤드커버 · 오른손용",
                 "받은 날부터 7일 이내 교환 · 반품"):
        centered(d, y, line, f, (200, 200, 204))
        y += 52
    centered(d, 1770, "grazr.co.kr", ImageFont.truetype(EN, 40), (245, 245, 247))
    im.save(out, quality=94)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "brand"))
    a = ap.parse_args()
    buy_card(os.path.join(a.out, "instagram_story_buy.jpg"))
