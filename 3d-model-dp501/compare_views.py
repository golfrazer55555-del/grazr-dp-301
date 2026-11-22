"""QA: overlay the owner's drawings / reference photos on the orthographic check renders (same mm scale).

  python3 3d-model-dp501/build_dp501.py --ortho     (writes check/*.png, 10 px/mm, centre at X 0, Y 46, Z 28)
  python3 3d-model-dp501/compare_views.py           (writes check/compare_*.jpg)

Each sheet: render | drawing | overlay (render in grey, the drawing's outline in red).
"""
import os

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "grazr dp-501 parkgolf photo")
CHK = os.path.join(HERE, "check")
PPM, C = 10.0, 650.0                        # render px per mm, image centre
HC = (0.0, 46.0, 28.0)
K_Y, K_Z = 95.0 / 94.4, 56.0 / 53.0


def warp(src, sx, sy, ox, oy, size=1300):
    """Affine: drawing pixel (x, y) -> render pixel (u, v) = (sx * x + ox, sy * y + oy)."""
    M = np.float32([[sx, 0, ox], [0, sy, oy]])
    return cv2.warpAffine(src, M, (size, size), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))


def edges(img):
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    m = (g < 200).astype(np.uint8) * 255
    return cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0


def sheet(name, render, drawing):
    r = np.asarray(Image.open(os.path.join(CHK, render + ".png")).convert("RGB"))
    over = (r.astype(np.float32) * 0.85).astype(np.uint8)
    e = edges(drawing)
    over[e] = (255, 30, 30)
    out = np.concatenate([r, drawing, over], 1)
    Image.fromarray(out).resize((1950, 650)).save(os.path.join(CHK, "compare_" + name + ".jpg"), quality=88)


def load(n):
    return np.asarray(Image.open(os.path.join(SRC, n)).convert("RGB"))


def main():
    # top: drawing face edge x=167 -> Y=0; centre row 444.5 -> X=0; 7.274 px/mm along Y, 7.189 along X
    d = load("head-top-design.jpg")
    sx, sy = PPM / 7.274, PPM / 7.189
    sheet("top", "top", warp(d, sx, sy, C + (0 - HC[1]) * PPM - 167 * sx, C - 444.5 * sy))
    # heel: face x=158 -> Y=0, sole y=492 -> Z=0; 7.30 px/mm
    d = load("head-side-left-design.jpg")
    sx, sy = PPM * K_Y / 7.30, PPM * K_Z / 7.30
    sheet("heel", "heel", warp(d, sx, sy, C + (0 - HC[1]) * PPM - 158 * sx, C + HC[2] * PPM - 492 * sy))
    # toe: face x=812 -> Y=0 (on the right), sole y=506 -> Z=0; 7.90 px/mm
    d = load("head-side-right-design.jpg")
    sx, sy = PPM * K_Y / 7.90, PPM * K_Z / 7.90
    sheet("toe", "toe", warp(d, sx, sy, C - (0 - HC[1]) * PPM - 812 * sx, C + HC[2] * PPM - 506 * sy))
    # bottom: face y=170 -> Y=0 (top), centre x=491 -> X=0; 6.55 px/mm
    d = load("head-bottom-design.jpg")
    s = PPM / 6.55
    sheet("bottom", "bottom", warp(d, s, s, C - 491 * s, C + (0 - HC[1]) * PPM - 170 * s))
    # front: detail-page face photo (134): centre x=523.5, sole y=597, 5.54 px/mm across, 5.34 px/mm up
    p = os.path.join(os.path.dirname(HERE), "..", "tmp")
    face = os.environ.get("FACE_IMG")
    if face and os.path.exists(face):
        d = np.asarray(Image.open(face).convert("RGB"))
        sx, sy = PPM / 5.538, PPM / 5.34
        sheet("front", "front", warp(d, sx, sy, C - 523.5 * sx, C + HC[2] * PPM - 597 * sy))
    # back: reference photo (head-back.png): centre x=1018.5, sole y=1400, 12.35 px/mm; heel on the left
    d = load("head-back.png")
    d = np.where(d.max(2, keepdims=True) > 14, 70, 255).astype(np.uint8)
    s = PPM / 12.35
    sheet("back", "back", warp(d, s, s, C - 1018.5 * s, C + HC[2] * PPM - 1400 * s))


if __name__ == "__main__":
    main()
