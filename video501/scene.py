"""GRAZR DP-501 - 3D promo film (Blender / Cycles, bpy 5.3).

Every frame is a pure function of time t (video seconds): cameras, lights, the swing and the ball are
set in Python and rendered with Cycles from 3d-model-dp501/dp501_parkgolf.blend.
The edit is locked to "Flower Duet" (Golden Cut Reborn): the music starts at its first note (0.441 s),
one shot per 16-beat phrase (two half-phrase shots in phrase 2), and at video 43.015 s the music
jumps to the song's ending (153.379 s) where the 8 beats before match; the logo comes in on the
closing phrase (compose.py).

  python3 video501/scene.py --stills 3,9,13,18,26,34,41 --quality preview --out OUT
  python3 video501/scene.py --shot brass --quality final --out video501/frames
  python3 video501/scene.py --frames 0-1115 --step 2 --quality preview --out OUT
"""
import argparse
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "..", "3d-model-dp501", "dp501_parkgolf.blend")

FPS = 24
M0 = 0.441                            # first note of the song = video 0
# beat grid of the recording (librosa, eighth-note pulse ~117 BPM, slightly rubato): every 16th beat
BEAT16 = [0.441, 7.802, 15.302, 22.976, 30.674, 38.383]
P = [b - M0 for b in BEAT16]          # phrase starts, video seconds
SPLICE = 43.456 - M0                  # 43.015 s: jump to the ending (song 153.379 s)
T_IMPACT = 41.424 - M0                # 40.983 s: impact on beat 86 (the club is at address when the shot opens)
SHOTS = [                             # name, start, end (video seconds)
    ("reveal", P[0], P[1]),                         # PREMIUM MAPLE TREE
    ("face", P[1], 0.5 * (P[1] + P[2])),            # full carbon face
    ("toe", 0.5 * (P[1] + P[2]), P[2]),             # PARKER 300 UNIT LIMITED EDITION
    ("brass", P[2], P[3]),                          # rear brass weight
    ("sole", P[3], P[4]),                           # gold-engraved brass sole
    ("shaft", P[4], P[5]),                          # aiming line: down the shaft to the head top
    ("stroke", P[5], SPLICE),                       # easier, more precise
    ("finale", SPLICE, 47.2),                       # certified club, over the song's closing phrase
]
END_3D = 47.2                         # the logo takes over (compose.py)
LAST_FRAME = int(round(END_3D * FPS)) - 1


def shot_at(t):
    for name, a, b in SHOTS:
        if t < b:
            return name, a, b
    return SHOTS[-1]


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lin(t, a, b):
    return clamp((t - a) / (b - a))


def ease(x):                        # smootherstep
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def ease_io(x):                     # gentle sine in/out
    return 0.5 - 0.5 * math.cos(math.pi * clamp(x))


def lerp(a, b, x):
    return a + (b - a) * x


def vlerp(a, b, x):
    return Vector(a).lerp(Vector(b), x)


def look_euler(loc, target, roll=0.0, up=(0, 0, 1)):
    f = (Vector(target) - Vector(loc)).normalized()
    up = Vector(up)
    if abs(f.dot(up.normalized())) > 0.999:
        up = Vector((0, 1, 0))
    r = f.cross(up).normalized()
    u = r.cross(f)
    m = Matrix((r, u, -f)).transposed()
    return (m @ Matrix.Rotation(math.radians(roll), 3, "Z")).to_euler()


# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
with bpy.data.libraries.load(MODEL, link=False) as (src, dst):
    dst.objects = list(src.objects)
for o in dst.objects:
    sc.collection.objects.link(o)
ROOT = bpy.data.objects["GRAZR_DP501"]
CLUB = [bpy.data.objects[n] for n in ("DP501_Shaft", "DP501_Grip", "DP501_GripCap")]
HEAD = bpy.data.objects["DP501_Head"]
HEAD_PARTS = [HEAD] + [o for o in bpy.data.objects if o.name.startswith(("DP501_FacePin", "DP501_Ferrule"))]
MM = 0.001
LIFT = 0.0002                      # keep the sole off the floor plane (no coplanar faces)

# model geometry (mm, standing pose; build_dp501.py)
LIE = math.radians(75.0)
D_SHAFT = Vector((math.cos(LIE), 0.0, math.sin(LIE)))
P0_MM = Vector((-2.0, 30.1, 0.0))                    # shaft axis meets the sole plane
FRONT = Vector((-math.sin(LIE), 0.0, math.cos(LIE)))  # the shaft print faces the toe side
HC = Vector((0.0, 0.046, 0.028))                     # head centre (m)
FACE_C = Vector((0.0, 0.0, 0.028))                   # face centre (m)
BACK_C = Vector((0.0, 0.084, 0.026))                 # brass weight
STAND = Matrix.Translation((0, 0, LIFT)) @ Matrix.Diagonal((MM, MM, MM, 1.0))


def axis_pt(s_mm):
    """World point on the shaft axis s_mm from the sole plane (standing pose)."""
    return (P0_MM + D_SHAFT * s_mm) * MM + Vector((0, 0, LIFT))


def mat(name, color, rough, metallic=0.0, coat=0.0, coat_rough=0.05):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = coat_rough
    return m, b


# floor: deep black, softly glossy, fading to black away from the product
floor_me = bpy.data.meshes.new("floor")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=12.0)
bm.to_mesh(floor_me)
bm.free()
FLOOR = bpy.data.objects.new("Floor", floor_me)
sc.collection.objects.link(FLOOR)
m_floor = bpy.data.materials.new("Floor_BlackSatin")
m_floor.use_nodes = True
nt = m_floor.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt.nodes.remove(n)
f_diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
f_diff.inputs["Color"].default_value = (0.018, 0.018, 0.019, 1)
f_gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
f_gloss.inputs["Color"].default_value = (1, 1, 1, 1)
nz = nt.nodes.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 3.0
mr = nt.nodes.new("ShaderNodeMapRange")
mr.inputs["To Min"].default_value = 0.10
mr.inputs["To Max"].default_value = 0.20
nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], f_gloss.inputs["Roughness"])
f_mix = nt.nodes.new("ShaderNodeMixShader")
f_mix.inputs["Fac"].default_value = 0.08
nt.links.new(f_diff.outputs["BSDF"], f_mix.inputs[1])
nt.links.new(f_gloss.outputs["BSDF"], f_mix.inputs[2])
tco = nt.nodes.new("ShaderNodeTexCoord")
FLOOR_C = nt.nodes.new("ShaderNodeCombineXYZ")
sub = nt.nodes.new("ShaderNodeVectorMath")
sub.operation = "SUBTRACT"
dist = nt.nodes.new("ShaderNodeVectorMath")
dist.operation = "LENGTH"
FLOOR_FADE = nt.nodes.new("ShaderNodeMapRange")
FLOOR_FADE.interpolation_type = "SMOOTHERSTEP"
black = nt.nodes.new("ShaderNodeBsdfDiffuse")
black.inputs["Color"].default_value = (0, 0, 0, 1)
mix = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(tco.outputs["Object"], sub.inputs[0])
nt.links.new(FLOOR_C.outputs["Vector"], sub.inputs[1])
nt.links.new(sub.outputs["Vector"], dist.inputs[0])
nt.links.new(dist.outputs["Value"], FLOOR_FADE.inputs["Value"])
nt.links.new(FLOOR_FADE.outputs["Result"], mix.inputs["Fac"])
nt.links.new(f_mix.outputs["Shader"], mix.inputs[1])
nt.links.new(black.outputs["BSDF"], mix.inputs[2])
nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
FLOOR.data.materials.append(m_floor)


def floor_pool(cx, cy, r0, r1):
    FLOOR_C.inputs["X"].default_value = cx
    FLOOR_C.inputs["Y"].default_value = cy
    FLOOR_FADE.inputs["From Min"].default_value = r0
    FLOOR_FADE.inputs["From Max"].default_value = r1


# park golf ball: 60 mm, smooth glossy plastic
def make_ball(r=0.030):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=r)
    me = bpy.data.meshes.new("ball")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Ball", me)
    sc.collection.objects.link(ob)
    m, _ = mat("Ball_Ivory", (0.88, 0.86, 0.80), 0.22, coat=0.8, coat_rough=0.04)
    me.materials.append(m)
    return ob


BALL_R = 0.030
BALL = make_ball(BALL_R)

# world: pure black studio
world = bpy.data.worlds.new("black")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
sc.world = world

# lights (positions / power are set per frame)
LIGHTS = {}


def add_light(name, kind="AREA", size=(0.3, 0.3)):
    li = bpy.data.lights.new(name, kind)
    if kind == "AREA":
        li.shape = "RECTANGLE"
        li.size, li.size_y = size
    ob = bpy.data.objects.new(name, li)
    ob.visible_camera = False
    sc.collection.objects.link(ob)
    LIGHTS[name] = ob
    return ob


for nm, sz in (("key", (0.5, 0.5)), ("fill", (0.6, 0.4)), ("rimL", (0.9, 0.035)), ("rimR", (0.9, 0.035)),
               ("top", (0.7, 0.03)), ("sweep", (0.6, 0.025)), ("soft", (0.8, 0.6))):
    add_light(nm, size=sz)
# rims / top / sweep / soft shape the club only: their reflections smear on the floor at low angles
NO_FLOOR = bpy.data.collections.new("NoFloor")
NO_FLOOR.objects.link(FLOOR)
NO_FLOOR.collection_objects[0].light_linking.link_state = "EXCLUDE"
for nm in ("rimL", "rimR", "top", "sweep", "soft"):
    LIGHTS[nm].light_linking.receiver_collection = NO_FLOOR
# face softbox: lights only the head (its reflection lays a sheen on the carbon weave and the lacquer)
add_light("face", size=(0.5, 0.35))
FACE_ONLY = bpy.data.collections.new("HeadOnly")
for o in HEAD_PARTS:
    FACE_ONLY.objects.link(o)
LIGHTS["face"].light_linking.receiver_collection = FACE_ONLY

cam_data = bpy.data.cameras.new("cam")
cam_data.clip_start = 0.005
cam_data.sensor_width = 36.0
CAM = bpy.data.objects.new("Camera", cam_data)
sc.collection.objects.link(CAM)
sc.camera = CAM

ENERGY = 0.12                      # global light scale


def light(name, loc, target, power, size=None):
    ob = LIGHTS[name]
    power *= ENERGY
    ob.hide_render = power <= 0
    ob.location = loc
    ob.rotation_euler = look_euler(loc, target)
    ob.data.energy = max(power, 0.0)
    if size:
        ob.data.size, ob.data.size_y = size


def lights_off(*names):
    for n in names:
        light(n, (0, 0, 1), (0, 0, 0), 0)


def camera(loc, target, lens, fstop=None, focus=None, roll=0.0, up=(0, 0, 1)):
    CAM.location = loc
    CAM.rotation_euler = look_euler(loc, target, roll, up)
    cam_data.lens = lens
    cam_data.dof.use_dof = fstop is not None
    if fstop is not None:
        cam_data.dof.aperture_fstop = fstop
        cam_data.dof.focus_distance = focus if focus else (Vector(target) - Vector(loc)).length


def show(club=True, floor=True, ball=False):
    for o in CLUB:
        o.hide_render = not club
    FLOOR.hide_render = not floor
    BALL.hide_render = not ball


def mirror_light(name, surf_c, surf_n, power, off=0.0, side=0.0, dist=0.45, size=None):
    """Put a softbox where the surface mirrors the camera, tilted `off` degrees: off = 0 lays the
    sheen right across it, larger offsets keep only its soft edge."""
    n = Vector(surf_n).normalized()
    v = (CAM.location - Vector(surf_c)).normalized()
    r = (2.0 * n.dot(v) * n - v).normalized()
    if off:
        ax = r.cross(Vector((0, 0, 1)))
        if ax.length < 1e-6:
            ax = Vector((1, 0, 0))
        r = Matrix.Rotation(math.radians(off), 3, ax.normalized()) @ r
    if side:
        r = Matrix.Rotation(math.radians(side), 3, "Z") @ r
    light(name, Vector(surf_c) + r * dist, surf_c, power, size)


# ------------------------------------------------------------------ swing kinematics
# Pendulum in the swing plane (shaft line + target line); the pivot sits above the hands.
AXIS = D_SHAFT.cross(Vector((0, 1, 0))).normalized()    # +angle moves the head toward the target (-Y)
PIVOT = axis_pt(1150.0)
PHI_B = 0.22                                            # backswing (rad, ~13 deg)
PHI_F = 0.16                                            # held finish (rad)
SWING = 1.30                                            # top of backswing -> impact (s), unhurried
OMEGA = math.pi / (2 * SWING)


def swing_phi(t):
    """Address, take-away, impact at T_IMPACT, then a held follow-through."""
    t_top = T_IMPACT - SWING
    if t < t_top - 1.0:
        return 0.0
    if t < t_top:                                       # slow take-away to the top
        return -PHI_B * ease_io(lin(t, t_top - 1.0, t_top))
    if t < T_IMPACT:                                    # down through the ball
        return -PHI_B * math.cos(OMEGA * (t - t_top))
    w = PHI_B * OMEGA / PHI_F                           # same speed at impact, eases into the finish
    return PHI_F * math.sin(w * min(t - T_IMPACT, math.pi / (2 * w)))


def swing_matrix(phi):
    R = Matrix.Rotation(phi, 4, AXIS)
    return Matrix.Translation(PIVOT) @ R @ Matrix.Translation(-PIVOT) @ STAND


HEAD_SPEED = PHI_B * OMEGA * (HC - PIVOT).cross(AXIS).length
V0 = 1.4 * HEAD_SPEED
DECEL = 0.12
BALL_Y0 = -BALL_R - 0.0015                              # just in front of the face at address


def ball_state(t):
    d = 0.0
    if t > T_IMPACT:
        dt = min(t - T_IMPACT, V0 / DECEL)
        d = V0 * dt - 0.5 * DECEL * dt * dt
    return Vector((0.0, BALL_Y0 - d, BALL_R + LIFT)), d / BALL_R


def face_at(t):
    m = Matrix.Translation(PIVOT) @ Matrix.Rotation(swing_phi(t), 4, AXIS) @ Matrix.Translation(-PIVOT)
    return m @ (FACE_C + Vector((0, 0, LIFT)))


# ------------------------------------------------------------------ shots
def pose_reveal(t, a, b):
    """Out of the dark: rims trace the maple head, a sweep crosses the top, the face sheen comes up;
    slow push-in from the toe-front."""
    u = ease_io(lin(t, a, b))
    show()
    ROOT.matrix_world = STAND
    floor_pool(0.0, 0.04, 0.16, 0.50)
    d = Vector((-0.30, -0.24, 0.13)).normalized()
    camera(HC + d * lerp(0.62, 0.44, u), HC + Vector((0.006, 0.0, lerp(0.010, 0.004, u))), 60, fstop=5.6)
    rim = ease(lin(t, 0.3, 2.4))
    light("rimL", (-0.36, 0.30, 0.16), HC, 70 * rim)
    light("rimR", (0.38, 0.34, 0.18), HC, 55 * rim)
    sx = lerp(-0.40, 0.40, ease_io(lin(t, 1.4, 6.0)))
    light("sweep", (sx, -0.02, 0.34), (sx * 0.25, 0.04, 0.0), 45 * ease(lin(t, 1.0, 2.2)))
    light("key", (-0.30, -0.36, 0.46), HC, 32 * ease(lin(t, 2.8, 6.4)))
    mirror_light("face", FACE_C, (0, -1, 0), 120 * ease(lin(t, 2.0, 5.4)), off=10.0)
    lights_off("top", "fill", "soft")


def pose_face(t, a, b):
    """Close along the carbon face: the weave's sheen moves as the camera slides toe -> heel."""
    u = ease_io(lin(t, a, b))
    show()
    ROOT.matrix_world = STAND
    floor_pool(0.0, 0.0, 0.10, 0.30)
    x = lerp(-0.026, 0.022, u)
    loc = Vector((x - 0.075, -0.200, 0.058))
    camera(loc, Vector((x, 0.0, 0.026)), 85, fstop=8.0)
    mirror_light("face", (x, 0.0, 0.028), (0, -1, 0), 16, off=30.0, side=lerp(-10.0, 10.0, u), dist=0.5)
    light("rimR", (0.36, 0.32, 0.16), HC, 40)
    light("top", (0.0, 0.20, 0.45), HC, 6)
    lights_off("key", "fill", "rimL", "sweep", "soft")


def pose_toe(t, a, b):
    """Along the toe side: PARKER 300 UNIT / LIMITED EDITION and the GR mark, a light sweep crossing."""
    u = ease_io(lin(t, a, b))
    show()
    ROOT.matrix_world = STAND
    floor_pool(-0.05, 0.04, 0.12, 0.40)
    y = lerp(0.020, 0.052, u)
    loc = Vector((-0.235, y - 0.030, 0.050))
    camera(loc, Vector((-0.05, y, 0.030)), 85, fstop=8.0)
    sy = lerp(-0.25, 0.35, ease_io(lin(t, a + 0.1, b - 0.1)))
    light("sweep", (-0.40, sy, 0.26), (-0.05, sy * 0.3 + 0.03, 0.02), 40, size=(0.025, 0.6))
    mirror_light("face", (-0.052, 0.040, 0.032), (-1, 0, 0), 90, off=14.0, dist=0.5)
    light("rimR", (0.30, 0.40, 0.25), HC, 35)
    lights_off("key", "fill", "rimL", "top", "soft")


def pose_brass(t, a, b):
    """Slow orbit round the back: the brass weight from the heel side to behind the head."""
    u = ease_io(lin(t, a, b))
    show()
    ROOT.matrix_world = STAND
    floor_pool(0.0, 0.08, 0.14, 0.45)
    ang = math.radians(lerp(35.0, -18.0, u))           # 0 = straight behind (+Y)
    r = lerp(0.36, 0.31, u)
    loc = BACK_C + Vector((r * math.sin(ang), r * math.cos(ang), lerp(0.095, 0.075, u)))
    camera(loc, BACK_C + Vector((0.0, -0.012, 0.0)), 85, fstop=6.3)
    light("soft", BACK_C + Vector((-0.20, 0.10, 0.32)), BACK_C, 75, size=(0.45, 0.45))
    light("fill", BACK_C + Vector((0.32, 0.12, 0.04)), BACK_C, 25)
    light("rimL", BACK_C + Vector((-0.30, -0.30, 0.20)), BACK_C, 45)
    light("rimR", BACK_C + Vector((0.30, -0.30, 0.22)), BACK_C, 45)
    sx = lerp(0.35, -0.35, ease_io(lin(t, a + 1.0, b - 0.5)))
    light("sweep", (sx, 0.40, 0.25), BACK_C, 35, size=(0.025, 0.6))
    lights_off("key", "top", "face")


def pose_sole(t, a, b):
    """The head turned over, floating: the brass sole and its gold-glitter engraving catch a sweeping light."""
    u = ease_io(lin(t, a, b))
    show(club=False, floor=False)
    for o in HEAD_PARTS:
        if o.name.startswith("DP501_Ferrule"):
            o.hide_render = True
    centre = Vector((0.0, 0.0, 0.14))
    spin = math.radians(lerp(-24.0, 10.0, u))
    tilt = math.radians(-112.0)
    hc_m = Vector((0.0, 46.0, 28.0))
    ROOT.matrix_world = (Matrix.Translation(centre) @ Matrix.Rotation(spin, 4, "Z") @ Matrix.Rotation(tilt, 4, "X")
                         @ Matrix.Diagonal((MM, MM, MM, 1.0)) @ Matrix.Translation(-hc_m))
    camera(Vector((0.0, -0.34, 0.20 - 0.012 * u)), centre + Vector((0, 0, 0.004)), 75, fstop=6.3)
    sx = lerp(-0.45, 0.45, ease_io(lin(t, a + 0.3, b - 0.3)))
    light("sweep", (sx, -0.28, 0.30), centre, 34)
    light("top", (0.0, -0.05, 0.55), centre, 12)
    light("rimL", (-0.30, 0.25, 0.25), centre, 40)
    light("rimR", (0.30, 0.25, 0.20), centre, 40)
    light("fill", (0.25, -0.35, 0.05), centre, 4)
    lights_off("key", "soft", "face")


def pose_shaft(t, a, b):
    """Down the shaft: the printed aiming graphic slides past, then the head top and its aiming line."""
    u = ease_io(lin(t, a, b))
    show()
    ROOT.matrix_world = STAND
    floor_pool(0.0, 0.04, 0.18, 0.55)
    s = lerp(430.0, 70.0, u)                             # mm along the shaft (print band 200-450)
    p = axis_pt(s)
    side = FRONT * lerp(0.20, 0.10, u) + Vector((0.0, -lerp(0.05, 0.18, u), lerp(0.0, 0.16, u)))
    tgt = p.lerp(HC + Vector((0.0, 0.0, 0.02)), ease_io(lin(t, a + 3.2, b)))
    camera(p + side, tgt, lerp(85, 55, u), fstop=8.0, up=tuple(D_SHAFT.lerp(Vector((0, 0, 1)), u)))
    light("rimL", p + Vector((-0.30, -0.25, 0.25)), p, 45)
    light("rimR", p + Vector((0.30, 0.30, 0.20)), p, 40)
    light("soft", p + FRONT * 0.35 + Vector((0, -0.25, 0.20)), p, 30, size=(0.5, 0.8))
    light("top", HC + Vector((0.0, -0.05, 0.45)), HC, 14 * ease(lin(t, a + 3.0, b)))
    mirror_light("face", HC + Vector((0, 0, 0.026)), (0, 0, 1), 30 * ease(lin(t, a + 3.5, b)), off=26.0)
    lights_off("key", "fill", "sweep")


def pose_stroke(t, a, b):
    """Side view from the toe: address, take-away, impact on the beat; the ball rolls out of frame
    toward the target and the finish is held."""
    show(ball=True)
    floor_pool(0.0, -0.20, 0.30, 0.95)
    ROOT.matrix_world = swing_matrix(swing_phi(t))
    bc, roll = ball_state(t)
    BALL.matrix_world = Matrix.Translation(bc) @ Matrix.Rotation(-roll, 4, "X")
    drift = ease_io(lin(t, a, b))
    cam = Vector((-0.80, lerp(-0.01, -0.05, drift), 0.090))
    camera(cam, Vector((0.0, lerp(-0.01, -0.05, drift), 0.060)), 46, fstop=8.0, focus=0.80)
    light("key", (-0.55, -0.20, 0.70), (0, -0.05, 0.0), 55)
    light("rimL", (0.10, 0.45, 0.20), HC, 60)
    light("rimR", (0.45, -0.45, 0.20), (0, -0.10, 0.03), 45)
    light("top", (0.0, -0.05, 0.50), (0, -0.05, 0.0), 10)
    light("soft", (-0.60, 0.10, 0.25), HC, 20, size=(0.6, 0.4))
    lights_off("fill", "sweep", "face")


def pose_finale(t, a, b):
    """The club standing at address, a slow rising orbit from the face round to the heel side
    (GRAZR / GOLF RAZER), rim light on the maple, under the song's closing phrase."""
    u = ease_io(lin(t, a, b + 1.5))
    show()
    ROOT.matrix_world = STAND
    floor_pool(0.02, 0.04, 0.18, 0.60)
    ang = math.radians(lerp(-150.0, -105.0, u))        # around the head, 0 = +X (heel)
    r = lerp(0.48, 0.40, u)
    loc = HC + Vector((r * math.cos(ang) * -1.0, r * math.sin(ang), lerp(0.10, 0.14, u)))
    camera(loc, HC + Vector((0.0, 0.0, 0.012)), 55, fstop=5.6)
    light("rimL", (-0.38, 0.34, 0.20), HC, 70)
    light("rimR", (0.40, 0.36, 0.22), HC, 60)
    light("key", (0.30, -0.40, 0.50), HC, 30)
    sx = lerp(0.40, -0.40, ease_io(lin(t, a + 0.4, b)))
    light("sweep", (sx, 0.0, 0.34), (sx * 0.25, 0.04, 0.0), 40)
    mirror_light("face", HC + Vector((0.053, 0.0, 0.0)), (1, 0, 0), 60, off=16.0)
    lights_off("top", "fill", "soft")


POSES = {"reveal": pose_reveal, "face": pose_face, "toe": pose_toe, "brass": pose_brass, "sole": pose_sole,
         "shaft": pose_shaft, "stroke": pose_stroke, "finale": pose_finale}

DEFAULT_RIM = (0.9, 0.035)
DEFAULT_SWEEP = (0.6, 0.025)


def pose(t):
    name, a, b = shot_at(t)
    for nm in ("rimL", "rimR"):
        LIGHTS[nm].data.size, LIGHTS[nm].data.size_y = DEFAULT_RIM
    LIGHTS["sweep"].data.size, LIGHTS["sweep"].data.size_y = DEFAULT_SWEEP
    for o in HEAD_PARTS:
        o.hide_render = False
    lights_off("face")
    POSES[name](t, a, b)
    return name


# ------------------------------------------------------------------ render settings
QUALITY = {
    "preview": dict(res=(960, 540), samples=12, threshold=0.06),
    "draft": dict(res=(1920, 1080), samples=24, threshold=0.04),
    "final": dict(res=(1920, 1080), samples=24, threshold=0.04),
}
VERTICAL_K = 0.88
VERTICAL = False


def setup_render(q, vertical=False):
    c = QUALITY[q]
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = c["res"]
    global VERTICAL
    VERTICAL = vertical
    if vertical:
        r.resolution_x, r.resolution_y = r.resolution_y, r.resolution_x
        cam_data.sensor_fit = "HORIZONTAL"
        cam_data.sensor_width = 36.0 * VERTICAL_K
    r.resolution_percentage = 100
    r.use_persistent_data = True
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = c["samples"]
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = c["threshold"]
    cy.use_denoising = True
    cy.denoising_quality = "BALANCED"
    cy.denoising_prefilter = "FAST"
    cy.max_bounces = 4
    cy.diffuse_bounces = 1
    cy.glossy_bounces = 2
    cy.transmission_bounces = 2
    cy.transparent_max_bounces = 8
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 4.0
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0


def render_frame(f, out):
    t = f / FPS
    name = pose(t)
    sc.frame_current = f
    sc.cycles.seed = f
    sc.render.filepath = os.path.join(out, f"{f:04d}.png")
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"frame {f:4d} t={t:6.3f} {name:7s} {time.time() - t0:6.1f}s", flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", default="preview", choices=QUALITY)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shot")
    ap.add_argument("--frames")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--stills")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--vertical", action="store_true", help="9:16 frames (1080x1920) for Shorts / Reels")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    setup_render(a.quality, a.vertical)
    if a.stills:
        for t in (float(x) for x in a.stills.split(",")):
            pose(t)
            sc.render.filepath = os.path.join(a.out, f"still_{t:06.2f}.png")
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"still t={t} {time.time() - t0:.1f}s", flush=True)
        return
    if a.shot:
        _, s0, s1 = next(s for s in SHOTS if s[0] == a.shot)
        f0, f1 = int(round(s0 * FPS)), int(round(s1 * FPS)) - 1
    elif a.frames:
        f0, f1 = (int(x) for x in a.frames.split("-"))
    else:
        f0, f1 = 0, LAST_FRAME
    for f in range(f0, f1 + 1, a.step):
        if a.skip_existing and os.path.exists(os.path.join(a.out, f"{f:04d}.png")):
            continue
        render_frame(f, a.out)


if __name__ == "__main__":
    main()
