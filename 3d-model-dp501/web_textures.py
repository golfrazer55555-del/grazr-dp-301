"""Textures for the web model (glTF): the render materials mix decals, masks and procedural glitter in Blender nodes,
which glTF cannot carry, so the same mixes are done here into plain images.

  base colour (sRGB), metal-rough (G roughness, B metallic, glTF layout), tangent-space normal maps (OpenGL, +Y up)

Called by build_dp501.py --web with the render materials' own constants, so both stay in step."""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")


def to_lin(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def load(name, mode="RGBA"):
    return np.asarray(Image.open(os.path.join(TEX, name)).convert(mode)).astype(np.float64) / 255.0


def save_rgb(a, path, size=None, srgb=False):
    a = to_srgb(a) if srgb else np.clip(a, 0.0, 1.0)
    im = Image.fromarray(np.round(a * 255).astype(np.uint8), "RGB")
    if size and im.size != size:
        im = im.resize(size, Image.LANCZOS)
    im.save(path)
    return path


def mr(rough, metal):
    """glTF metallic-roughness image: R unused (1), G roughness, B metallic."""
    rough = np.broadcast_to(rough, np.shape(metal) if np.ndim(metal) else np.shape(rough))
    metal = np.broadcast_to(metal, rough.shape)
    return np.stack([np.ones_like(rough), rough, metal], -1)


def normal_map(h, mm_per_px_u, mm_per_px_v, scale, wrap=False):
    """Tangent-space normal from a height field h (0..1, image rows run down = -v); scale = bump distance (mm)
    times strength, so the slope is scale * dh/dmm."""
    if wrap:
        du = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * mm_per_px_u)
        dv = -(np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * mm_per_px_v)
    else:
        g0, g1 = np.gradient(h)
        du, dv = g1 / mm_per_px_u, -g0 / mm_per_px_v
    n = np.stack([-scale * du, -scale * dv, np.ones_like(h)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def encode_n(n):
    return n * 0.5 + 0.5


def decal(name, out, black, size=None):
    """Lacquer with a printed decal: base = decal over black, gold ink metallic (r - b), printed areas satin."""
    d = load(name)
    a = d[..., 3:4]
    col = to_lin(d[..., :3])
    base = col * a + np.asarray(black[:3]) * (1 - a)    # the render colours (black ...) are linear already
    k = np.clip(2 * (col[..., 0] - col[..., 2]), 0, 1) * a[..., 0]
    paths = (save_rgb(base, out + ".png", size, srgb=True),
             save_rgb(mr(0.12 + 0.18 * a[..., 0], 0.55 * k), out + "_mr.png", size))
    return paths


def sole(out, brass, glit, black, head_w, head_d, seed=501):
    """Brass sole plate: brushed brass, engraving filled with gold glitter (random shade / roughness / tilt per
    flake of about 1 / glit['scale'] mm), dark rim round the engraving, black DP-501."""
    e = load("sole_engrave.png", "L")
    k = load("sole_black.png", "L")
    r = load("sole_rings.png", "L")
    H, W = e.shape
    mu, mv = head_w / W, head_d / H                      # mm per pixel
    rng = np.random.default_rng(seed)
    cell = 1.0 / glit["scale"]                           # flake size, mm
    gh, gw = int(np.ceil(H * mv / cell)), int(np.ceil(W * mu / cell))
    yy = np.minimum((np.arange(H) * mv / cell).astype(int), gh - 1)
    xx = np.minimum((np.arange(W) * mu / cell).astype(int), gw - 1)
    rnd = rng.random((4, gh, gw))[:, yy][:, :, xx]       # per flake: shade, roughness, tilt u, tilt v
    shade = glit["shade"] + (1 - glit["shade"]) * rnd[0]
    gold = np.asarray(glit["color"][:3]) * shade[..., None]
    base = np.asarray(brass[:3]) * (1 - e[..., None]) + gold * e[..., None]
    base = base * (1 - r[..., None]) + np.array([0.05, 0.03, 0.006]) * r[..., None]
    base = base * (1 - k[..., None]) + np.asarray(black[:3]) * k[..., None]
    rough = 0.27 * (1 - e) + (glit["rough"][0] + (glit["rough"][1] - glit["rough"][0]) * rnd[1]) * e
    rough = rough * (1 - k) + 0.45 * k
    metal = 1.0 - k
    # recessed engraving (height 1 - max(engrave, rim)), bump 0.12 mm x 0.6, plus each flake's own tilt
    n = normal_map(1.0 - np.maximum(e, r), mu, mv, 0.12 * 0.6)
    t = (rnd[2:4] - 0.5) * glit["tilt"]
    n = n + np.stack([t[0], t[1], np.zeros_like(e)], -1) * e[..., None]
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (save_rgb(base, out + ".png", srgb=True), save_rgb(mr(rough, metal), out + "_mr.png"),
            save_rgb(encode_n(n), out + "_n.png"))


def carbon(out, navy, size=512):
    """Carbon weave tile (4.33 x 4.22 mm): shade from the face photo x navy, rougher across the tows, tow bump."""
    sh = load("carbon_shade.png", "RGB")
    c = load("carbon.png", "RGB")
    warp, height = c[..., 0], c[..., 1]
    base = sh * np.asarray(navy[:3])
    H, W = height.shape
    n = normal_map(height, 4.33 / W, 4.22 / H, 0.2 * 0.2, wrap=True)
    s = (size, size)
    return (save_rgb(base, out + ".png", s, srgb=True), save_rgb(mr(0.40 - 0.10 * warp, np.full_like(warp, 0.3)),
                                                                  out + "_mr.png", s),
            save_rgb(encode_n(n), out + "_n.png", s))


def grip(out, grip_len, circ, size=(512, 2048)):
    """Grip rubber: albedo as rendered, pyramid bump (1.1 mm x 1.2) as a normal map."""
    alb = Image.open(os.path.join(TEX, "grip_albedo.png")).convert("RGB")
    alb.resize(size, Image.LANCZOS).save(out + ".png")
    b = load("grip_bump.png", "L")
    H, W = b.shape
    n = normal_map(b, circ / W, grip_len / H, 1.1 * 1.2, wrap=True)
    return out + ".png", save_rgb(encode_n(n), out + "_n.png", size)


def shaft(out, black, size=(4096, 684)):
    """Shaft print (shaft_print.py): base over the black lacquer, metallic per ink from shaft_wrap_metal.png."""
    im = Image.open(os.path.join(TEX, "shaft_wrap.png")).convert("RGBA").resize(size, Image.LANCZOS)
    d = np.asarray(im).astype(np.float64) / 255.0
    met = np.asarray(Image.open(os.path.join(TEX, "shaft_wrap_metal.png")).convert("L").resize(size, Image.LANCZOS))
    a = d[..., 3:4]
    base = to_lin(d[..., :3]) * a + np.asarray(black[:3]) * (1 - a)
    base[:, :2] = base[:, -2:] = black[:3]               # clamped edges stay black outside the printed band
    return (save_rgb(base, out + ".png", srgb=True),
            save_rgb(mr(0.1 + 0.12 * a[..., 0], met.astype(np.float64) / 255.0), out + "_mr.png"))


def cap(out, size=(512, 512)):
    Image.open(os.path.join(TEX, "grip_cap.png")).convert("RGB").resize(size, Image.LANCZOS).save(out + ".png")
    return out + ".png"
