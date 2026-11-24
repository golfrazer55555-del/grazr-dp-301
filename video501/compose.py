"""Composite the GRAZR DP-501 film: 3D frames + copy + logo end card + music.

  python3 video501/compose.py --frames video501/frames --out video501/out/GRAZR_DP-501_film.mp4
  python3 video501/compose.py --frames PREVIEW_DIR --size 960x540 --out preview.mp4

Frames are the PNGs written by scene.py. Missing frames (e.g. a preview rendered with --step 2) reuse the
nearest earlier frame. The edit is locked to "Flower Duet" (Golden Cut Reborn), see scene.py.
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
T_LOGO = 47.2                        # = scene.END_3D: the logo over the song's closing bars
LAST_3D = int(round(T_LOGO * FPS)) - 1

MUSIC = os.path.join(HERE, "audio", "Flower Duet - Golden Cut Reborn.mp3")
LOGO = os.path.join(ROOT, "grazr dp-301 putter photo", "logo.png")
F_EN = os.path.join(HERE, "fonts", "Montserrat_400Regular.ttf")
F_KR = os.path.join(HERE, "fonts", "Pretendard-Light.otf")

# music edit: from the first note through four phrases and a half, then - 30 ms before both beats, where
# the 8 beats before match (chroma 0.83) - onto the song's closing bars, which ring out under the logo
M_A0 = 0.441                         # first note -> video 0.0
M_A1 = 43.456 - 0.030                # beat 90
M_B0 = 153.379 - 0.030               # beat 316 of the ending
M_END = 161.2                        # the last chord has died away
DURATION = round((M_A1 - M_A0) + (M_END - M_B0), 3)   # ~50.8 s

# copy: (in, out, english, korean, layout)
COPY = [
    (3.40, 6.95, "PREMIUM MAPLE TREE", "300개 한정 프리미엄 파크골프채", "bottom"),
    (7.85, 10.85, "FULL CARBON FACE", "풀 카본 페이스, 부드러운 타구감", "bottom"),
    (11.55, 14.55, "LIMITED TO 300", "단 300개만 만든 한정판", "bottom"),
    (16.10, 21.90, "REAR BRASS WEIGHT", "후면 황동추, 낮고 깊은 무게중심", "bottom"),
    (23.90, 29.60, "GOLD-ENGRAVED BRASS SOLE", "금빛 각인을 새긴 황동 바닥", "bottom"),
    (31.40, 37.40, "MAPLE AIMING LINE", "헤드와 샤프트의 조준 라인으로 정확하게", "bottom"),
    (38.40, 42.70, "EASIER, MORE PRECISE", "더 쉽게, 더 정교하게", "top"),
    (43.60, 46.90, "CERTIFIED CLUB", "(사)대한파크골프협회 공인인증", "bottom"),
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


def _greedy(words, font, tracking, max_w):
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and tracked(t, font, tracking).width > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + [cur]


def wrap(text, font, tracking, max_w):
    """Word wrap for the Korean line (vertical layout): fewest lines, then as even as possible."""
    words = text.split(" ")
    lines = _greedy(words, font, tracking, max_w)
    n, w = len(lines), max_w
    while n > 1 and w > 40:               # shrink the box while the line count holds
        trial = _greedy(words, font, tracking, w - 20)
        if len(trial) != n:
            break
        lines, w = trial, w - 20
    return lines


def stack(masks, gap):
    w = max(m.width for m in masks)
    h = sum(m.height for m in masks) + gap * (len(masks) - 1)
    out = Image.new("L", (w, h), 0)
    y = 0
    for m in masks:
        out.paste(m, ((w - m.width) // 2, y))
        y += m.height + gap
    return out


class Overlay:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.vertical = H > W
        k = W / 1920.0 if not self.vertical else 1.0
        self.k = k
        self.f_en = ImageFont.truetype(F_EN, int(round(44 * k)) if not self.vertical else 40)
        self.f_kr = ImageFont.truetype(F_KR, int(round(30 * k)) if not self.vertical else 36)
        self.blocks = []
        yy = np.arange(H, dtype=np.float32) / H
        self.shade = np.clip((yy - 0.62) / 0.30, 0, 1) ** 1.5
        if self.vertical:                            # copy band above the Shorts / Reels caption area
            self.shade = np.exp(-((yy - 0.66) / 0.10) ** 2) * 0.9
        for t0, t1, en, kr, layout in COPY:
            if self.vertical:
                layout = "bottom"
                m_en = np.asarray(tracked(en, self.f_en, 9), np.float32) / 255.0
                m_kr = np.asarray(stack([tracked(l, self.f_kr, 1) for l in wrap(kr, self.f_kr, 1, int(W * 0.84))], 14),
                                  np.float32) / 255.0
            else:
                m_en = np.asarray(tracked(en, self.f_en, 14 * k), np.float32) / 255.0
                m_kr = np.asarray(tracked(kr, self.f_kr, 2 * k), np.float32) / 255.0
            gap = int(round(22 * k))
            bw = max(m_en.shape[1], m_kr.shape[1])
            bh = m_en.shape[0] + gap + m_kr.shape[0]
            if layout == "bottom":
                cx, top = W // 2, int(H * (0.66 if self.vertical else 0.845)) - bh // 2
            elif layout == "top":
                cx, top = W // 2, int(H * (0.66 if self.vertical else 0.16)) - bh // 2
            else:                                    # right half, vertically centred
                cx, top = int(W * 0.765), H // 2 - bh // 2
            items = [(m_en, cx - m_en.shape[1] // 2, top, 0.96),
                     (m_kr, cx - m_kr.shape[1] // 2, top + m_en.shape[0] + gap, 0.80)]
            self.blocks.append((t0, t1, items, bw, bh, layout))
        # logo (content bbox of logo.png)
        lg = Image.open(LOGO).convert("RGBA")
        lg = lg.crop(lg.getchannel("A").getbbox())
        lh = int(round(300 * k)) if not self.vertical else 330
        lg = lg.resize((int(round(lg.width * lh / lg.height)), lh), Image.LANCZOS)
        a = np.asarray(lg, np.float32) / 255.0
        self.logo_rgb, self.logo_a = a[..., :3], a[..., 3:]
        self.logo_pos = ((W - lg.width) // 2, int(H * 0.475) - lh // 2)
        yy, xx = np.mgrid[0:lg.height, 0:lg.width].astype(np.float32)
        self.logo_diag = (xx + 0.6 * yy) / (lg.width + 0.6 * lg.height)
        f_sub = ImageFont.truetype(F_EN, int(round(30 * k)) if not self.vertical else 34)
        sub = np.asarray(tracked("DP-501  ·  PARK GOLF", f_sub, (12 * k) if not self.vertical else 10), np.float32) / 255.0
        self.sub = sub
        self.sub_pos = ((W - sub.shape[1]) // 2, self.logo_pos[1] + lh + int(round(46 * k if not self.vertical else 50)))

    def text(self, img, t):
        for t0, t1, items, bw, bh, layout in self.blocks:
            if not (t0 <= t <= t1):
                continue
            fi, fo = min(0.9, (t1 - t0) / 4), min(0.7, (t1 - t0) / 5)
            a = ease((t - t0) / fi) * (1.0 - ease((t - (t1 - fo)) / fo))
            if layout == "bottom" or (layout == "top" and self.vertical):   # soft shade keeps the copy legible
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
        a = ease(u / 1.0) * (1.0 - ease((t - (DURATION - 0.95)) / 0.9))
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
        sa = ease((u - 0.9) / 1.0) * (1.0 - ease((t - (DURATION - 0.95)) / 0.9)) * 0.75
        if sa > 0:
            sx, sy = self.sub_pos
            sh, sw = self.sub.shape
            m = (self.sub * sa)[..., None]
            reg = img[sy:sy + sh, sx:sx + sw]
            reg[:] = reg * (1 - m) + np.array([0.86, 0.72, 0.45], np.float32) * m


def frame_path(frames, f):
    while f >= 0:
        p = os.path.join(frames, f"{f:04d}.png")
        if os.path.exists(p):
            return p
        f -= 1
    return None


def audio_filter():
    a_len = M_A1 - M_A0
    return (
        f"[1:a]atrim=start={M_A0}:end={M_A1},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d=0.03,afade=t=out:st={a_len - 0.015:.3f}:d=0.015[ma];"
        f"[2:a]atrim=start={M_B0}:end={M_END},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.012[mb];"
        f"[ma][mb]concat=n=2:v=0:a=1,afade=t=out:st={DURATION - 1.2:.3f}:d=1.2,"
        f"alimiter=limit=0.89:level=false,atrim=end={DURATION}[aout]"
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
           "-i", MUSIC, "-i", MUSIC,
           "-filter_complex", audio_filter(),
           "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "slow", "-crf", a.crf, "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-c:a", "aac", "-b:a", "320k", "-t", str(DURATION), a.out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(DURATION * FPS))
    last, cur = None, None
    rng = np.random.default_rng(501)
    dither = [(rng.random((H, W, 1), np.float32) - 0.5) * (1.2 / 255) for _ in range(8)]
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
        img += dither[f % len(dither)]                # break up banding in the dark gradients
        ff.stdin.write((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        if f % 120 == 0:
            print(f"compose {f}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done:", a.out)


if __name__ == "__main__":
    main()
