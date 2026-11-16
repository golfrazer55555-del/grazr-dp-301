"""Feature short clips (16:9) cut from the GRAZR DP-301 film, plus a thumbnail for each.

  python3 video3d/shorts.py --frames video3d/frames --film video3d/out/GRAZR_DP-301_film.mp4 --out video3d/out/shorts

Each clip is one feature section of the film (cut on the music's bar lines) followed by the
logo end card on the song's final hit. Picture comes from the rendered PNG frames (no re-encode
loss); sound is cut from the finished film, so the music duck and impact sound stay as mixed.
"""
import argparse
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import compose as C

FPS = C.FPS
BAR, PHRASE = C.BAR, C.PHRASE
SPLICE = C.M_A1 - C.M_A0          # film time of the splice onto the final hit (30 ms before it)
TAIL = 3.6                        # logo end card length
F_KR_B = os.path.join(C.HERE, "fonts", "Pretendard-Regular.otf")
F_EN_M = os.path.join(C.HERE, "fonts", "Montserrat_500Medium.ttf")

# (file, start, end, thumbnail frame, thumbnail headline, thumbnail sub line)
CLIPS = [
    ("01_cnc_milled_face", 2 * BAR, PHRASE + 2 * BAR, 250, "다이아몬드 밀링 페이스", "100% FULL CNC MILLED"),
    ("02_forged_sus304", PHRASE + 2 * BAR, 2 * PHRASE, 300, "단조 SUS304 헤드", "FORGED SUS304 STAINLESS"),
    ("03_crisp_sound", 2 * PHRASE, 3 * PHRASE, 396, "맑고 청량한 타구음", "PURE, CRISP SOUND"),
    ("04_center_shaft", 3 * PHRASE, 4 * PHRASE, 572, "흔들림 없는 직진성", "CENTER SHAFT"),
    ("05_stands_alone", 4 * PHRASE, 5 * PHRASE, 760, "받침 없이 혼자 섭니다", "STANDS ON ITS OWN"),
    ("06_ball_pickup", 5 * PHRASE, 6 * PHRASE, 915, "허리 숙이지 않고 공 집기", "PICKS UP THE BALL"),
]


def frame(frames, ov, n):
    img = np.asarray(Image.open(C.frame_path(frames, n)).convert("RGB"), np.float32) / 255.0
    img = img.copy()
    ov.text(img, n / FPS)
    return img


def make_clip(a, ov, dither, name, t0, t1):
    f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    n_body, n_tail = f1 - f0, int(round(TAIL * FPS))
    dur = (n_body + n_tail) / FPS
    body = n_body / FPS
    out = os.path.join(a.out, name + ".mp4")
    af = (f"[1:a]atrim={t0:.3f}:{t0 + body - 0.031:.3f},asetpts=PTS-STARTPTS[b];"
          f"[1:a]atrim={SPLICE:.3f}:{SPLICE + TAIL + 0.1:.3f},asetpts=PTS-STARTPTS[l];"
          f"[b][l]acrossfade=d=0.012:c1=tri:c2=tri,"
          f"afade=t=in:d=0.25,afade=t=out:st={dur - 0.9:.3f}:d=0.9,atrim=end={dur:.3f}[aout]")
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", str(FPS), "-i", "-",
           "-i", a.film, "-filter_complex", af, "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-c:a", "aac", "-b:a", "320k", "-t", f"{dur:.3f}", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n_body + n_tail):
        if i < n_body:
            img = frame(a.frames, ov, f0 + i)
        else:
            img = np.zeros((1080, 1920, 3), np.float32)
            ov.logo(img, C.T_LOGO + (i - n_body) / FPS)
        t = i / FPS
        img *= C.ease(t / 0.15) * (1.0 - C.ease((t - (dur - 0.8)) / 0.8))
        img += dither[i % len(dither)]
        ff.stdin.write((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
    ff.stdin.close()
    ff.wait()
    print(f"{out}  {dur:.2f}s")


def make_thumb(a, name, n, head, sub):
    im = Image.open(C.frame_path(a.frames, n)).convert("RGB")
    img = np.asarray(im, np.float32) / 255.0
    # darken the lower band so the headline reads on any frame
    yy = np.linspace(0, 1, 1080, dtype=np.float32)[:, None, None]
    img = img * (1.0 - 0.75 * np.clip((yy - 0.55) / 0.35, 0, 1) ** 1.3)
    im = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    d = ImageDraw.Draw(im)
    f_kr = ImageFont.truetype(F_KR_B, 108)
    f_en = ImageFont.truetype(F_EN_M, 38)
    f_br = ImageFont.truetype(F_EN_M, 30)
    w = d.textlength(head, font=f_kr)
    d.text(((1920 - w) / 2, 840), head, font=f_kr, fill=(245, 245, 245))
    sub_m = C.tracked(sub, f_en, 10)
    im.paste((215, 215, 215), ((1920 - sub_m.width) // 2, 780), sub_m)
    br = C.tracked("GRAZR DP-301", f_br, 8)
    im.paste((200, 200, 200), (60, 52), br)
    im = im.resize((1280, 720), Image.LANCZOS)
    p = os.path.join(a.out, name + "_thumb.jpg")
    im.save(p, quality=92)
    print(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--film", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="comma list of clip numbers, e.g. 1,3")
    ap.add_argument("--thumbs-only", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ov = C.Overlay(1920, 1080)
    rng = np.random.default_rng(301)
    dither = [(rng.random((1080, 1920, 1), np.float32) - 0.5) * (1.2 / 255) for _ in range(8)]
    only = {int(x) for x in a.only.split(",") if x}
    for i, (name, t0, t1, tn, head, sub) in enumerate(CLIPS, 1):
        if only and i not in only:
            continue
        make_thumb(a, name, tn, head, sub)
        if not a.thumbs_only:
            make_clip(a, ov, dither, name, t0, t1)


if __name__ == "__main__":
    main()
