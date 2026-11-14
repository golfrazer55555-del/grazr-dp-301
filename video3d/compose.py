"""Composite the GRAZR DP-301 film: 3D frames + copy + logo end card + music.

  python3 video3d/compose.py --frames video3d/frames --out video3d/out/GRAZR_DP-301_film.mp4
  python3 video3d/compose.py --frames PREVIEW_DIR --size 960x540 --out preview.mp4

Frames are the PNGs written by scene.py (0000.png ... 0703.png). Missing frames
(e.g. a preview rendered with --step 2) reuse the nearest earlier frame.
The edit is locked to "Stairway" by Patrick Patrikios (see scene.py for the grid).
"""
import argparse
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FPS = 24
DURATION = 35.0
BEAT = 0.45808
BAR = 4 * BEAT
PHRASE = 4 * BAR
T_IMPACT = 2 * PHRASE + BAR          # 16.49 s
T_LOGO = 4 * PHRASE                  # 29.317 s, the final hit
LAST_3D = int(round(T_LOGO * FPS)) - 1

MUSIC = os.path.join(HERE, "audio", "Stairway - Patrick Patrikios.mp3")
HIT = os.path.join(ROOT, "Putter-sound.m4a")
LOGO = os.path.join(ROOT, "grazr dp-301 putter photo", "logo.png")
F_EN = os.path.join(HERE, "fonts", "Montserrat_400Regular.ttf")
F_KR = os.path.join(HERE, "fonts", "Pretendard-Light.otf")

# music edit: intro from a phrase start, spliced (30 ms before both transients) onto the song's final hit
M_A0 = 14.869                        # phrase start  -> video 0.0
M_A1 = 44.185 - 0.030                # just before the intro's closing hit
M_B0 = 161.313 - 0.030               # just before the final hit (rings out to silence)
HIT_PEAK = 0.303                     # peak inside Putter-sound.m4a after trimming 1.0 s

# copy: (in, out, english, korean, layout)
COPY = [
    (8.15, 14.15, "PRECISION YOU CAN SEE", "한눈에 느껴지는 완성도", "bottom"),
    (18.70, 21.75, "PURE, CRISP SOUND", "맑고 청량한 타구음", "bottom"),
    (24.40, 28.95, "STANDS ON ITS OWN", "바닥에 놓으면, 스스로 섭니다", "right"),
]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def tracked(text, font, tracking, fill=255):
    """Render text with letter spacing into an L-mode mask (tight bbox)."""
    widths = [font.getlength(ch) for ch in text]
    w = int(math.ceil(sum(widths) + tracking * (len(text) - 1))) + 8
    asc, desc = font.getmetrics()
    m = Image.new("L", (w, asc + desc + 8), 0)
    d = ImageDraw.Draw(m)
    x = 4.0
    for ch, cw in zip(text, widths):
        d.text((x, 4), ch, font=font, fill=fill)
        x += cw + tracking
    return m.crop(m.getbbox())


class Overlay:
    def __init__(self, W, H):
        self.W, self.H = W, H
        k = W / 1920.0
        self.k = k
        self.f_en = ImageFont.truetype(F_EN, int(round(44 * k)))
        self.f_kr = ImageFont.truetype(F_KR, int(round(30 * k)))
        self.blocks = []
        yy = np.arange(H, dtype=np.float32) / H
        self.shade = np.clip((yy - 0.62) / 0.30, 0, 1) ** 1.5
        for t0, t1, en, kr, layout in COPY:
            m_en = np.asarray(tracked(en, self.f_en, 14 * k), np.float32) / 255.0
            m_kr = np.asarray(tracked(kr, self.f_kr, 2 * k), np.float32) / 255.0
            gap = int(round(22 * k))
            bw = max(m_en.shape[1], m_kr.shape[1])
            bh = m_en.shape[0] + gap + m_kr.shape[0]
            if layout == "bottom":
                cx, top = W // 2, int(H * 0.845) - bh // 2
            else:                                    # right half, vertically centred
                cx, top = int(W * 0.70), H // 2 - bh // 2
            items = [(m_en, cx - m_en.shape[1] // 2, top, 0.96),
                     (m_kr, cx - m_kr.shape[1] // 2, top + m_en.shape[0] + gap, 0.80)]
            self.blocks.append((t0, t1, items, bw, bh, layout))
        # logo (content bbox of logo.png)
        lg = Image.open(LOGO).convert("RGBA")
        lg = lg.crop(lg.getchannel("A").getbbox())
        lh = int(round(300 * k))
        lg = lg.resize((int(round(lg.width * lh / lg.height)), lh), Image.LANCZOS)
        a = np.asarray(lg, np.float32) / 255.0
        self.logo_rgb, self.logo_a = a[..., :3], a[..., 3:]
        self.logo_pos = ((W - lg.width) // 2, int(H * 0.475) - lh // 2)
        yy, xx = np.mgrid[0:lg.height, 0:lg.width].astype(np.float32)
        self.logo_diag = (xx + 0.6 * yy) / (lg.width + 0.6 * lg.height)

    def text(self, img, t):
        for t0, t1, items, bw, bh, layout in self.blocks:
            if not (t0 <= t <= t1):
                continue
            a = ease((t - t0) / 0.9) * (1.0 - ease((t - (t1 - 0.7)) / 0.7))
            if layout == "bottom":                  # soft lower-third shade keeps the copy legible
                img *= (1.0 - 0.55 * a * self.shade)[:, None, None]
            drift = int(round((1.0 - ease((t - t0) / 1.6)) * 10 * self.k))
            for m, x, y, op in items:
                y += drift
                h, w = m.shape
                region = img[y:y + h, x:x + w]
                al = (m * (a * op))[..., None]
                region[:] = region * (1 - al) + al

    def logo(self, img, t):
        u = t - T_LOGO
        a = ease(u / 1.0) * (1.0 - ease((t - 34.05) / 0.9))
        if a <= 0:
            return
        x, y = self.logo_pos
        h, w = self.logo_a.shape[:2]
        # faint bloom behind the mark on the hit
        glow = 0.10 * math.exp(-max(u, 0) / 0.9) * a
        if glow > 0.002:
            H, W = img.shape[:2]
            yy, xx = np.ogrid[0:H, 0:W]
            cy, cx = y + h / 2, x + w / 2
            r = np.sqrt(((yy - cy) / (H * 0.45)) ** 2 + ((xx - cx) / (W * 0.30)) ** 2)
            img += (glow * np.clip(1 - r, 0, 1) ** 2)[..., None]
        rgb = self.logo_rgb.copy()
        s = (u - 1.0) / 1.5                          # one slow specular pass across the mark
        if 0 < s < 1:
            band = np.exp(-((self.logo_diag - (-0.2 + 1.4 * s)) / 0.07) ** 2)[..., None]
            rgb = np.clip(rgb + 0.55 * band, 0, 1)
        al = self.logo_a * a
        region = img[y:y + h, x:x + w]
        region[:] = region * (1 - al) + rgb * al


def frame_path(frames, f):
    while f >= 0:
        p = os.path.join(frames, f"{f:04d}.png")
        if os.path.exists(p):
            return p
        f -= 1
    return None


def audio_filter():
    duck = "1-0.62*min(max((t-16.22)/0.2,0),1)*min(max((17.95-t)/0.85,0),1)"
    a_len = M_A1 - M_A0
    b_len = DURATION - a_len + 0.3
    return (
        f"[1:a]atrim=start={M_A0}:end={M_A1},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d=0.25,afade=t=out:st={a_len - 0.015:.3f}:d=0.015[ma];"
        f"[2:a]atrim=start={M_B0}:duration={b_len:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.012[mb];"
        f"[ma][mb]concat=n=2:v=0:a=1,volume='{duck}':eval=frame,"
        f"afade=t=out:st={DURATION - 1.1}:d=1.1[mus];"
        f"[3:a]atrim=start=1.0,asetpts=PTS-STARTPTS,volume=1.25,"
        f"adelay={int(round((T_IMPACT - HIT_PEAK) * 1000))}:all=1[hit];"
        f"[mus][hit]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=false,"
        f"atrim=end={DURATION}[aout]"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--crf", default="16")
    a = ap.parse_args()
    W, H = (int(v) for v in a.size.split("x"))
    ov = Overlay(W, H)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", MUSIC, "-i", MUSIC, "-i", HIT,
           "-filter_complex", audio_filter(),
           "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "slow", "-crf", a.crf, "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-c:a", "aac", "-b:a", "320k", "-t", str(DURATION), a.out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(DURATION * FPS))
    last, cur = None, None
    for f in range(n):
        t = f / FPS
        if f <= LAST_3D:
            p = frame_path(a.frames, f)
            if p != last or cur is None:
                src = Image.open(p).convert("RGB")
                if src.size != (W, H):
                    src = src.resize((W, H), Image.LANCZOS)
                cur = np.asarray(src, np.float32) / 255.0
                last = p
            img = cur.copy()
        else:
            img = np.zeros((H, W, 3), np.float32)
        ov.text(img, t)
        if f > LAST_3D:
            ov.logo(img, t)
        img *= ease(t / 0.9)                          # open from black
        ff.stdin.write((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        if f % 120 == 0:
            print(f"compose {f}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done:", a.out)


if __name__ == "__main__":
    main()
