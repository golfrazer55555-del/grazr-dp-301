"""Home-page card for the DP-501: the whole club standing in a soft light column, like the DP-301 card
(website/tools/render_stills.py full_black). Uses the film scene (video501/scene.py) for the model,
floor, lights and camera.

  python3 website/tools/render_card_501.py --out 3d-model-dp501/site/card_full.png
  python3 website/tools/render_card_501.py --out /tmp/x.png --preview
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT_DIR, "video501"))
sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:]]
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import scene as S  # noqa: E402

# soft vertical light column far behind the club (the black shaft reads against it), as on the DP-301 card
bd_me = bpy.data.meshes.new("backdrop")
bd_me.from_pydata([(-1.5, -1.5, 0), (1.5, -1.5, 0), (1.5, 1.5, 0), (-1.5, 1.5, 0)], [], [(0, 1, 2, 3)])
BACK = bpy.data.objects.new("Backdrop", bd_me)
S.sc.collection.objects.link(BACK)
m = bpy.data.materials.new("Backdrop_Glow")
m.use_nodes = True
nt = m.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt.nodes.remove(n)
tco = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tco.outputs["Object"], sep.inputs[0])
# glow = exp(-(x/wx)^2) * smoothstep falloff in y (brighter above), all in object space (metres)
sx = nt.nodes.new("ShaderNodeMath"); sx.operation = "DIVIDE"; sx.inputs[1].default_value = 0.60
nt.links.new(sep.outputs["X"], sx.inputs[0])
sq = nt.nodes.new("ShaderNodeMath"); sq.operation = "POWER"; sq.inputs[1].default_value = 2.0
nt.links.new(sx.outputs[0], sq.inputs[0])
ng = nt.nodes.new("ShaderNodeMath"); ng.operation = "MULTIPLY"; ng.inputs[1].default_value = -1.0
nt.links.new(sq.outputs[0], ng.inputs[0])
ex = nt.nodes.new("ShaderNodeMath"); ex.operation = "EXPONENT"
nt.links.new(ng.outputs[0], ex.inputs[0])
vy = nt.nodes.new("ShaderNodeMapRange"); vy.interpolation_type = "SMOOTHERSTEP"
vy.inputs["From Min"].default_value = -0.40
vy.inputs["From Max"].default_value = 0.40
nt.links.new(sep.outputs["Y"], vy.inputs["Value"])
top = nt.nodes.new("ShaderNodeMapRange"); top.interpolation_type = "SMOOTHERSTEP"
top.inputs["From Min"].default_value = 1.9
top.inputs["From Max"].default_value = 0.55
nt.links.new(sep.outputs["Y"], top.inputs["Value"])
mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
nt.links.new(ex.outputs[0], mul.inputs[0])
nt.links.new(vy.outputs["Result"], mul.inputs[1])
mul2 = nt.nodes.new("ShaderNodeMath"); mul2.operation = "MULTIPLY"
nt.links.new(mul.outputs[0], mul2.inputs[0])
nt.links.new(top.outputs["Result"], mul2.inputs[1])
STRENGTH = nt.nodes.new("ShaderNodeMath"); STRENGTH.operation = "MULTIPLY"
nt.links.new(mul2.outputs[0], STRENGTH.inputs[0])
em = nt.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (0.92, 0.92, 0.94, 1)
nt.links.new(STRENGTH.outputs[0], em.inputs["Strength"])
nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
BACK.data.materials.append(m)
for flag in ("visible_glossy", "visible_diffuse", "visible_shadow", "visible_transmission"):
    setattr(BACK, flag, False)


def pose(back_glow):
    S.show(club=True, floor=True, ball=False)
    S.ROOT.matrix_world = S.STAND
    for o in S.HEAD_PARTS:
        o.hide_render = False
    for ob in S.LIGHTS.values():
        ob.visible_glossy = True
    tgt = S.axis_pt(400.0) + Vector((0.0, 0.0, -0.01))
    d = Vector((-0.34, -0.94, 0.07)).normalized()
    cam = tgt + d * 1.30
    S.camera(cam, tgt, 45, fstop=8.0)
    # backdrop: behind the club, facing the camera, centred a little above the head
    back = tgt - d * 2.4
    BACK.location = (back.x, back.y, 0.42)
    n = (cam - back)
    BACK.rotation_euler = (math.radians(90), 0, math.atan2(n.x, -n.y))
    STRENGTH.inputs[1].default_value = back_glow
    S.floor_pool(S.HC.x, S.HC.y, 0.10, 0.50)
    hc = S.HC
    S.light("key", hc + Vector((0.02, 0.06, 1.15)), hc, 420, size=(0.55, 0.55))
    S.light("rimL", (-0.70, 0.55, 0.62), S.axis_pt(420), 150, size=(0.035, 1.6))
    S.light("rimR", (0.85, 0.35, 0.66), S.axis_pt(420), 130, size=(0.035, 1.6))
    S.light("soft", cam + Vector((-0.3, 0.1, 0.2)), S.axis_pt(380), 45, size=(0.8, 1.2))
    S.LIGHTS["soft"].visible_glossy = False
    S.light("top", hc + Vector((0.0, 0.10, 0.55)), hc, 12)
    S.mirror_light("face", S.FACE_C, (0, -1, 0), 60, off=18.0)
    S.lights_off("fill", "sweep")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--glow", type=float, default=0.06)
    a = ap.parse_args()
    S.setup_render("preview" if a.preview else "final")
    r = S.sc.render
    r.resolution_x, r.resolution_y = (480, 600) if a.preview else (1200, 1500)
    S.cam_data.sensor_fit = "AUTO"
    S.RES_ASPECT = r.resolution_y / r.resolution_x
    if not a.preview:
        S.sc.cycles.samples = 96
    pose(a.glow)
    r.filepath = a.out
    bpy.ops.render.render(write_still=True)
    print("wrote", a.out)


main()
