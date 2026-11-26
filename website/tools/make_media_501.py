"""DP-501 and brand-home media for the website -> website/public/media/{dp501,home,3d}.

  python3 website/tools/make_media_501.py                        # everything
  python3 website/tools/make_media_501.py --only hero,clips,film  # just the parts cut from the film

Real photos come from `grazr dp-501 parkgolf photo/`; extra owner images (headcover, certification sticker)
from `website/tools/src501/`. Renders (hero, full club, feature stills, 3D poster) from
`3d-model-dp501/site/` (build_dp501.py site shots), and the 3D model from `3d-model-dp501/dp501_parkgolf.glb`.
"""
import argparse
import os
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.dirname(HERE)
ROOT = os.path.dirname(WEB)
PHOTOS = os.path.join(ROOT, "grazr dp-501 parkgolf photo")
EXTRA = os.path.join(HERE, "src501")
RENDERS = os.path.join(ROOT, "3d-model-dp501", "site")
OUT = os.path.join(WEB, "public", "media", "dp501")
HOME = os.path.join(WEB, "public", "media", "home")
FILM = os.path.join(ROOT, "video501")
FPS = 24
# film shots (frame ranges of video501/frames, the final 1080p render) used on the page
HERO = (0, 176)                 # the reveal: scroll-driven sequence, every 2nd frame
CLIPS = {                       # each plays once when scrolled into view
    "limited": (267, 356),      # toe: PARKER 300 UNIT LIMITED EDITION (intro)
    "maple": (1033, 1132),      # the whole head turning (finale)
    "face": (177, 266),
    "brass": (357, 540),
    "sole": (541, 725),
    "shaft": (726, 838),        # down the shaft to the tip of the aiming line
    "aim": (842, 1032),         # head top, then the stroke
}


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
    for k, im in items.items():
        save_webp(im, os.path.join(OUT, "photos", k + ".webp"), 1400)
        save_webp(im, os.path.join(OUT, "photos", k + "-640.webp"), 640)
    # shaft and grip are long and thin: also a horizontal strip (rotated, tight crop) for wide tiles
    for k in ("shaft", "grip"):
        im = items[k].rotate(90, expand=True)
        a_ = np.asarray(im.convert("L"))
        ys, xs = np.nonzero(a_ > 28)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        padx, pady = 60, max(40, (y1 - y0) // 3)
        im = im.crop((max(0, x0 - padx), max(0, y0 - pady), min(im.width, x1 + padx), min(im.height, y1 + pady)))
        save_webp(im, os.path.join(OUT, "photos", k + "-strip.webp"), 1800)
        save_webp(im, os.path.join(OUT, "photos", k + "-strip-900.webp"), 900)


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


def film_frame(n, size, vertical=False):
    d = os.path.join(FILM, "frames_v" if vertical else "frames")
    return Image.open(os.path.join(d, f"{n:04d}.png")).convert("RGB").resize(size, Image.LANCZOS)


def hero():
    """Scroll sequence of the reveal shot: 16:9 frames for wide screens, 9:16 frames for phones."""
    picks = list(range(HERO[0], HERO[1] + 1, 2))
    sets = (("1600", (1600, 900), False, 80), ("960", (960, 540), False, 78),
            ("v1600", (900, 1600), True, 78), ("v960", (540, 960), True, 76))
    for name, size, vert, q in sets:
        d = os.path.join(OUT, "hero", name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        total = 0
        for i, n in enumerate(picks):
            path = os.path.join(d, f"{i:03d}.webp")
            film_frame(n, size, vert).save(path, "WEBP", quality=q, method=5)
            total += os.path.getsize(path)
        print("hero", name, len(picks), "frames", total // 1024, "KB")


def encode(frames, out):
    n = len(frames)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1280x720",
           "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "21",
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", f"{n / FPS:.3f}", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        ff.stdin.write(np.asarray(film_frame(f, (1280, 720)), np.uint8).tobytes())
    ff.stdin.close()
    if ff.wait():
        raise SystemExit(f"ffmpeg failed: {out}")


def clips():
    d = os.path.join(OUT, "clips")
    os.makedirs(d, exist_ok=True)
    for name, (a, b) in CLIPS.items():
        out = os.path.join(d, f"{name}.mp4")
        encode(list(range(a, b + 1)), out)
        film_frame(a, (1280, 720)).save(os.path.join(d, f"{name}.webp"), "WEBP", quality=76, method=5)
        print("clip", name, b - a + 1, "frames", os.path.getsize(out) // 1024, "KB")


def film():
    src = os.path.join(FILM, "out", "GRAZR_DP-501_film.mp4")
    out = os.path.join(OUT, "film.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c:v", "libx264", "-preset", "slow", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
    film_frame(156, (1600, 900)).save(os.path.join(OUT, "film-poster.webp"), "WEBP", quality=80, method=5)
    print("film", os.path.getsize(out) // 1024, "KB")


def headcover():
    """The owner's cut-out headcover photo (transparent background) for the dark gallery."""
    im = Image.open(os.path.join(EXTRA, "headcover-cutout.png")).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    side = int(max(im.size) * 1.12)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    for w in (1400, 640):
        t = sq.resize((w, w), Image.LANCZOS) if side > w else sq
        path = os.path.join(OUT, "photos", "cover" + ("" if w == 1400 else "-640") + ".webp")
        t.save(path, "WEBP", quality=86, method=6)
        print(path, t.size)


STEPS = {"photos": photos, "misc": misc, "renders": renders, "hero": hero, "clips": clips, "film": film,
         "headcover": headcover}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated steps: " + ",".join(STEPS))
    a = ap.parse_args()
    for k in (a.only.split(",") if a.only else STEPS):
        STEPS[k]()
