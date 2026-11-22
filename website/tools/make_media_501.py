"""DP-501 and brand-home media for the website -> website/public/media/{dp501,home,3d}.

  python3 website/tools/make_media_501.py

Real photos come from `grazr dp-501 parkgolf photo/`; extra owner images (headcover, certification sticker)
from `website/tools/src501/`. Renders (hero, full club, feature stills, 3D poster) from
`3d-model-dp501/site/` (build_dp501.py site shots), and the 3D model from `3d-model-dp501/dp501_parkgolf.glb`.
"""
import os
import shutil

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.dirname(HERE)
ROOT = os.path.dirname(WEB)
PHOTOS = os.path.join(ROOT, "grazr dp-501 parkgolf photo")
EXTRA = os.path.join(HERE, "src501")
RENDERS = os.path.join(ROOT, "3d-model-dp501", "site")
OUT = os.path.join(WEB, "public", "media", "dp501")
HOME = os.path.join(WEB, "public", "media", "home")


def save_webp(im, path, w, q=84):
    im = im.convert("RGB")
    if im.width > w:
        im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "WEBP", quality=q, method=6)
    print(path, im.size)


def square_photo(name, zoom=1.0, dy=0.0):
    im = Image.open(os.path.join(PHOTOS, name)).convert("RGB")
    if zoom != 1.0:
        w, h = im.size
        cw, ch = int(w / zoom), int(h / zoom)
        cx, cy = w // 2, int(h // 2 + dy * h)
        im = im.crop((cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2))
    return im


def photos():
    """Gallery (square, black background), 1400 + 640."""
    items = {
        "face": square_photo("head-front(face).png"),
        "top": square_photo("head-top.png"),
        "sole": square_photo("head-bottom.png"),
        "back": square_photo("head-back.png"),
        "toe": square_photo("head-right.png"),
        "heel": square_photo("head-left.png"),
        "shaft": square_photo("shaft-front-closeup.png"),
        "grip": square_photo("grip-front.png", zoom=1.0),
    }
    cover = os.path.join(EXTRA, "headcover.jpg")
    if os.path.exists(cover):
        im = Image.open(cover).convert("RGB")
        items["cover"] = ImageOps.pad(im, (max(im.size), max(im.size)), color=im.getpixel((5, 5)))
    for k, im in items.items():
        save_webp(im, os.path.join(OUT, "photos", k + ".webp"), 1400)
        save_webp(im, os.path.join(OUT, "photos", k + "-640.webp"), 640)


def renders():
    r = lambda n: os.path.join(RENDERS, n)
    if not os.path.isdir(RENDERS):
        print("no site renders yet:", RENDERS)
        return
    save_webp(Image.open(r("hero.png")), os.path.join(OUT, "hero.webp"), 1920, 86)
    save_webp(Image.open(r("hero_m.png")), os.path.join(OUT, "hero-m.webp"), 1080, 86)
    full = Image.open(r("full.png"))
    save_webp(full, os.path.join(OUT, "full.webp"), 1200)
    save_webp(full, os.path.join(OUT, "thumb-640.webp"), 640)
    card = Image.open(r("card.png"))
    save_webp(card, os.path.join(HOME, "dp501.webp"), 1200)
    save_webp(card, os.path.join(HOME, "dp501-640.webp"), 640)
    for k in ("brass", "maple", "shaft", "aim"):
        save_webp(Image.open(r("f_" + k + ".png")), os.path.join(OUT, "f-" + k + ".webp"), 1280)
    save_webp(Image.open(r("poster.png")), os.path.join(OUT, "poster.webp"), 1280)
    og = Image.open(r("hero.png")).convert("RGB")
    og = ImageOps.fit(og, (1200, 630), Image.LANCZOS)
    og.save(os.path.join(OUT, "og.jpg"), quality=88)


def misc():
    sticker = os.path.join(EXTRA, "cert.webp")
    if os.path.exists(sticker):
        save_webp(Image.open(sticker), os.path.join(OUT, "cert.webp"), 800)
    # home card for DP-301: the existing black-shaft product still
    src = os.path.join(WEB, "public", "media", "product")
    os.makedirs(HOME, exist_ok=True)
    shutil.copy(os.path.join(src, "full-black.webp"), os.path.join(HOME, "dp301.webp"))
    shutil.copy(os.path.join(src, "full-black-640.webp"), os.path.join(HOME, "dp301-640.webp"))
    glb = os.path.join(ROOT, "3d-model-dp501", "dp501_parkgolf.glb")
    if os.path.exists(glb):
        shutil.copy(glb, os.path.join(WEB, "public", "media", "3d", "dp501.glb"))


if __name__ == "__main__":
    photos()
    misc()
    renders()
