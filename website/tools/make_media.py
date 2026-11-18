"""Encode the website media into website/public/media.

  python3 website/tools/make_media.py                 # everything
  python3 website/tools/make_media.py --only hero,clips

Inputs (not all in git):
  video3d/frames/0000-1054.png      film frames  (python3 video3d/scene.py --quality final ...)
  website/.work/stills/*.png        shaft-option stills (python3 website/tools/render_stills.py ...)
  grazr dp-301 putter photo/*.png   product photos
  video3d/out/GRAZR_DP-301_film.mp4, video3d/out/GRAZR_DP-301_film_thumb.jpg, Putter-sound.m4a
  video3d/out/brand/GRAZR_profile_800.png, 3d-model/dp301_putter.glb
"""
import argparse
import os
import shutil
import subprocess

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
FRAMES = os.path.join(ROOT, "video3d", "frames")
STILLS = os.path.join(SITE, ".work", "stills")
PHOTOS = os.path.join(ROOT, "grazr dp-301 putter photo")
OUT = os.path.join(SITE, "public", "media")
FPS = 24

# film shots (frame ranges of the final film) used as the feature clips; each plays once
CLIPS = {
    "milling": (176, 263),
    "forged": (264, 351),
    "sound": (352, 527),       # impact at frame 396 (16.49 s)
    "center": (528, 703),
    "stand": (704, 879),
    "pickup": (880, 1054),
}
IMPACT_FRAME = 396
HIT = os.path.join(ROOT, "Putter-sound.m4a")
HIT_TRIM, HIT_PEAK = 1.0, 0.303      # as in video3d/compose.py: peak 0.303 s into the trimmed sound

PHOTO_SET = [
    ("face", "head-front(face).png"),
    ("sole", "head-bottom.png"),
    ("pickup-back", "behind surface of the ball head when picked up.png"),
    ("pickup-top", "Top surface of the ball head when picked up.png"),
    ("back", "head-behind.png"),
    ("weight", "weight.png"),
    ("cover", "head-cover.png"),
    ("grip", "putter-grip.png"),
    ("shaft", "putter-shaft.png"),
]


def frame(n, size=None):
    im = Image.open(os.path.join(FRAMES, f"{n:04d}.png")).convert("RGB")
    return im.resize(size, Image.LANCZOS) if size else im


def webp(im, path, q=78):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "WEBP", quality=q, method=5)


def hero():
    """Scroll sequence: the reveal shot, every 2nd frame, two sizes."""
    picks = list(range(0, 176, 2))
    for w, h, q in ((1600, 900, 82), (960, 540, 80)):
        d = os.path.join(OUT, "hero", str(w))
        shutil.rmtree(d, ignore_errors=True)
        for i, n in enumerate(picks):
            webp(frame(n, (w, h)), os.path.join(d, f"{i:03d}.webp"), q)
    print("hero", len(picks), "frames")


def encode(frames_iter, out, n, audio_filter=None):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1280x720",
           "-r", str(FPS), "-i", "-"]
    if audio_filter:
        cmd += ["-i", HIT, "-filter_complex", audio_filter, "-map", "0:v", "-map", "[a]",
                "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{n / FPS:.3f}", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for im in frames_iter:
        ff.stdin.write(np.asarray(im, np.uint8).tobytes())
    ff.stdin.close()
    if ff.wait():
        raise SystemExit(f"ffmpeg failed: {out}")


def clips():
    d = os.path.join(OUT, "clips")
    os.makedirs(d, exist_ok=True)
    for name, (a, b) in CLIPS.items():
        n = b - a + 1
        af = None
        if name == "sound":
            start = (IMPACT_FRAME - a) / FPS - HIT_PEAK
            ms = int(round(start * 1000))
            af = (f"[1:a]atrim=start={HIT_TRIM},asetpts=PTS-STARTPTS,adelay={ms}|{ms},"
                  f"apad,atrim=end={n / FPS:.3f}[a]")
        out = os.path.join(d, f"{name}.mp4")
        encode((frame(f, (1280, 720)) for f in range(a, b + 1)), out, n, af)
        webp(frame(a, (1280, 720)), os.path.join(d, f"{name}.webp"), 74)
        webp(frame(b, (1280, 720)), os.path.join(d, f"{name}-end.webp"), 74)
        print("clip", name, n, "frames", os.path.getsize(out) // 1024, "KB")


def stills():
    d = os.path.join(OUT, "product")
    os.makedirs(d, exist_ok=True)
    for kind in ("black", "silver"):
        im = Image.open(os.path.join(STILLS, f"full_{kind}.png")).convert("RGB")
        webp(im.resize((1200, 1500), Image.LANCZOS), os.path.join(d, f"full-{kind}.webp"), 82)
        webp(im.resize((640, 800), Image.LANCZOS), os.path.join(d, f"full-{kind}-640.webp"), 80)
    head = {"black": frame(150), "silver": Image.open(os.path.join(STILLS, "reveal_silver.png")).convert("RGB")}
    for kind, im in head.items():
        webp(im.resize((1600, 900), Image.LANCZOS), os.path.join(d, f"head-{kind}.webp"), 80)
        webp(im.resize((960, 540), Image.LANCZOS), os.path.join(d, f"head-{kind}-960.webp"), 78)
    # quiet frames reused around the page
    for name, n in (("macro", 230), ("top", 600), ("stand", 760), ("sole", 330)):
        webp(frame(n, (1600, 900)), os.path.join(d, f"{name}.webp"), 78)
    print("stills done")


def photos():
    d = os.path.join(OUT, "photos")
    os.makedirs(d, exist_ok=True)
    for name, f in PHOTO_SET:
        im = Image.open(os.path.join(PHOTOS, f)).convert("RGB")
        im.thumbnail((1400, 1400), Image.LANCZOS)
        webp(im, os.path.join(d, f"{name}.webp"), 80)
        t = im.copy()
        t.thumbnail((640, 640), Image.LANCZOS)
        webp(t, os.path.join(d, f"{name}-640.webp"), 78)
        print("photo", name, im.size)


def film():
    d = os.path.join(OUT, "film")
    os.makedirs(d, exist_ok=True)
    src = os.path.join(ROOT, "video3d", "out", "GRAZR_DP-301_film.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c:v", "libx264", "-preset", "slow", "-crf", "22",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                    os.path.join(d, "grazr-dp301-film.mp4")], check=True)
    webp(frame(150, (1600, 900)), os.path.join(d, "poster.webp"), 80)
    print("film", os.path.getsize(os.path.join(d, "grazr-dp301-film.mp4")) // 1024, "KB")


def icons():
    src = Image.open(os.path.join(ROOT, "video3d", "out", "brand", "GRAZR_profile_800.png")).convert("RGB")
    pub = os.path.join(SITE, "public")
    for size, name in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        src.resize((size, size), Image.LANCZOS).save(os.path.join(pub, name), optimize=True)
    src.resize((64, 64), Image.LANCZOS).save(os.path.join(pub, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    th = Image.open(os.path.join(ROOT, "video3d", "out", "GRAZR_DP-301_film_thumb.jpg")).convert("RGB")
    og = th.resize((1200, 675), Image.LANCZOS).crop((0, 22, 1200, 652))
    og.save(os.path.join(OUT, "og.jpg"), quality=88)
    print("icons + og done")


def model():
    d = os.path.join(OUT, "3d")
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "3d-model", "dp301_putter.glb"), os.path.join(d, "dp301.glb"))
    webp(frame(150, (1280, 720)), os.path.join(d, "poster.webp"), 78)
    print("model copied")


STEPS = {"hero": hero, "clips": clips, "stills": stills, "photos": photos, "film": film, "icons": icons,
         "model": model}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    for k in (a.only.split(",") if a.only else STEPS):
        STEPS[k]()
