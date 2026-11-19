"""Website stills from the film's dark studio (video3d/scene.py): the two shaft options.

  python3 website/tools/render_stills.py --out website/src/media/stills [--quality draft|preview]

  reveal_silver.png  - the film's reveal frame (t=6.25 s, frame 150) with the 33" silver shaft;
                       the 34" black version of the same frame is the film frame itself
  full_black.png / full_silver.png - the whole putter standing on its own (4:5)
The silver is a satin metallic paint sampled from the owner's photo of the 33" shaft
(the white GR logo and print are the same as on the black shaft).
"""
import argparse
import math
import os
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--quality", default="draft", choices=("draft", "preview"))
ap.add_argument("--only", default="")
args = ap.parse_args()
sys.argv = [sys.argv[0]]

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT_DIR, "video3d"))
import scene as S  # noqa: E402  (builds the studio on import)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

SHAFT = bpy.data.materials["Graphite_Shaft_GlossBlack"].node_tree.nodes["Principled BSDF"]
FINISH = {
    "black": {"Base Color": (0.004, 0.004, 0.004, 1), "Metallic": 0.0, "Roughness": 0.12,
              "Coat Weight": 1.0, "Coat Roughness": 0.03},
    "silver": {"Base Color": (0.13, 0.135, 0.145, 1), "Metallic": 0.5, "Roughness": 0.5,
               "Coat Weight": 0.0, "Coat Roughness": 0.22},
}
BLACK_COAT_ROUGH = SHAFT.inputs["Coat Roughness"].default_value
FINISH["black"]["Coat Roughness"] = BLACK_COAT_ROUGH


def shaft(kind):
    for k, v in FINISH[kind].items():
        SHAFT.inputs[k].default_value = v


def pose_full():
    """The whole putter standing on its own, front-left three-quarter view, slightly low."""
    S.show(club=True, floor=True, ball=False)
    S.target_line(0)
    S.ROOT.matrix_world = S.STAND
    S.floor_pool(0.06, 0.02, 0.28, 0.95)
    tgt = Vector((0.11, 0.02, 0.405))
    d = Vector((-0.30, -0.95, 0.06)).normalized()
    cam = tgt + d * 1.25
    S.camera(cam, tgt, 45, fstop=8.0)
    # soft light column straight behind the shaft: the black shaft reads as a silhouette
    back = tgt - d * 2.4
    n = (cam - back)
    S.backdrop((back.x, back.y, 0.0), 0.06, z0=-0.20, z1=0.95)
    S.BACKDROP.rotation_euler = (math.radians(90), 0, math.atan2(n.x, -n.y))
    S.light("spot", (0.06, 0.0, 1.6), (0.06, 0.02, 0.0), 1700)
    S.light("rimL", (-0.70, 0.55, 0.62), (0.11, 0.02, 0.42), 130, size=(0.035, 1.6))
    S.light("rimR", (0.85, 0.35, 0.66), (0.11, 0.02, 0.42), 120, size=(0.035, 1.6))
    S.light("keyNF", (-0.80, -0.95, 0.90), (0.08, 0.02, 0.35), 120)
    S.light("top", (0.14, 0.05, 1.30), (0.14, 0.02, 0.60), 14)
    S.lights_off("key", "fill", "rake", "sweep", "face")
    S._face_ref = (S.CAM.location.copy(), S.ROOT.matrix_world.copy())
    S.face_key(240)


def render(path, res, seed, spp):
    S.sc.render.resolution_x, S.sc.render.resolution_y = res
    S.sc.cycles.samples = spp
    S.sc.cycles.seed = seed
    S.sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"{os.path.basename(path)} {time.time() - t0:.1f}s", flush=True)


def main():
    os.makedirs(args.out, exist_ok=True)
    S.setup_render("draft")
    k = 1.0 if args.quality == "draft" else 0.5
    spp = 32 if args.quality == "draft" else 12
    only = set(args.only.split(",")) if args.only else None
    if not only or "reveal" in only:
        S.pose(6.25)                       # = film frame 150
        shaft("silver")
        render(os.path.join(args.out, "reveal_silver.png"), (int(1920 * k), int(1080 * k)), 150, 24)
    if not only or "full" in only:
        for kind in ("black", "silver"):
            pose_full()
            shaft(kind)
            render(os.path.join(args.out, f"full_{kind}.png"), (int(1200 * k), int(1500 * k)), 7, spp)
    shaft("black")


main()
