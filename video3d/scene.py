"""GRAZR DP-301 - 3D promo film (Blender / Cycles, bpy 5.3).

Every frame is a pure function of time t (video seconds): cameras, lights, the
putter stroke and the rolling ball are set in Python and rendered with Cycles.
The edit is locked to "Stairway" (131 BPM, 4-bar phrase = 7.329 s): one shot per
phrase, the impact on a downbeat, the logo (composited later) on the final hit.

  python3 video3d/scene.py --stills 3,9,12.8,16.6,25 --quality preview --out OUT
  python3 video3d/scene.py --shot reveal --quality final --out video3d/frames
  python3 video3d/scene.py --frames 0-1054 --step 2 --quality preview --out OUT
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
MODEL = os.path.join(HERE, "..", "3d-model", "dp301_putter.blend")

FPS = 24
BEAT = 0.45808                     # Stairway - Patrick Patrikios, ~131 BPM
BAR = 4 * BEAT                     # 1.832 s
PHRASE = 4 * BAR                   # 7.329 s
T_IMPACT = 2 * PHRASE + BAR        # 16.49 s - front impact on a downbeat (the featured sound)
T_IMPACT2 = 3 * PHRASE + BAR       # 23.82 s - the same stroke seen from above
T_PICK = 5 * PHRASE + BAR          # 38.48 s - the head clicks over the ball
SHOTS = [                          # name, start, end (video seconds) - one 4-bar phrase each
    ("reveal", 0.0, PHRASE),                    # look
    ("face", PHRASE, PHRASE + 2 * BAR),         # 100% CNC milling
    ("sole", PHRASE + 2 * BAR, 2 * PHRASE),     # forged SUS304 (sole engraving)
    ("stroke", 2 * PHRASE, 3 * PHRASE),         # crisp sound
    ("center", 3 * PHRASE, 4 * PHRASE),         # centre shaft: square head, straight roll
    ("stand", 4 * PHRASE, 5 * PHRASE),          # stands alone, alignment check from behind
    ("pickup", 5 * PHRASE, 6 * PHRASE),         # picks the ball up
]
END_3D = 6 * PHRASE                # 43.975 s - the logo takes over on the final hit
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


def look_euler(loc, target, roll=0.0):
    f = (Vector(target) - Vector(loc)).normalized()
    up = Vector((0, 0, 1)) if abs(f.z) < 0.999 else Vector((0, 1, 0))
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
ROOT = bpy.data.objects["GRAZR_DP301"]
CLUB = [bpy.data.objects[n] for n in ("DP301_Shaft", "DP301_Shaft_Print", "DP301_Grip")]
MM = 0.001
LIFT = 0.0002                      # keep the sole off the floor plane (no coplanar faces)

# model geometry we aim at (metres, standing pose)
LIE = math.radians(74.0)
D_SHAFT = Vector((math.cos(LIE), 0.0, math.sin(LIE)))
GROUND = Vector((0.0, 7.0, 25.0)) * MM - D_SHAFT * (0.025 / math.sin(LIE))
HC = Vector((0.0, 0.034, 0.0125))              # head centre
FACE_C = Vector((0.0, 0.0, 0.0125))            # face centre
STAND = Matrix.Translation((0, 0, LIFT)) @ Matrix.Diagonal((MM, MM, MM, 1.0))


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


# floor: deep black, softly glossy, with a faint roughness variation
floor_me = bpy.data.meshes.new("floor")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=12.0)
bm.to_mesh(floor_me)
bm.free()
FLOOR = bpy.data.objects.new("Floor", floor_me)
sc.collection.objects.link(FLOOR)
# Product-shot floor: very dark diffuse + a constant-strength soft reflection.
# (A physical glossy floor goes mirror-white at the low grazing camera angles we use.)
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
b_floor = f_mix
b_floor_out = f_mix.outputs["Shader"]
# fade the floor into pure black away from the product (centre / radii set per shot)
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
nt.links.new(b_floor_out, mix.inputs[1])
nt.links.new(black.outputs["BSDF"], mix.inputs[2])
nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
FLOOR.data.materials.append(m_floor)


def floor_pool(cx, cy, r0, r1):
    FLOOR_C.inputs["X"].default_value = cx
    FLOOR_C.inputs["Y"].default_value = cy
    FLOOR_FADE.inputs["From Min"].default_value = r0
    FLOOR_FADE.inputs["From Max"].default_value = r1


# soft vertical light column far behind the subject: the black shaft reads as a silhouette
bd_me = bpy.data.meshes.new("backdrop")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=3.0)
bm.to_mesh(bd_me)
bm.free()
BACKDROP = bpy.data.objects.new("Backdrop", bd_me)
sc.collection.objects.link(BACKDROP)
BACKDROP.rotation_euler = (math.radians(90), 0, 0)      # local X = world X, local Y = world Z
m_bd = bpy.data.materials.new("Backdrop_Glow")
m_bd.use_nodes = True
bnt = m_bd.node_tree
for n in list(bnt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        bnt.nodes.remove(n)


def _node(kind, **inputs):
    n = bnt.nodes.new(kind)
    for k, v in inputs.items():
        if k == "op":
            n.operation = v
        elif k == "interp":
            n.interpolation_type = v
        else:
            n.inputs[k].default_value = v
    return n


btc = _node("ShaderNodeTexCoord")
bsep = _node("ShaderNodeSeparateXYZ")
babs = _node("ShaderNodeMath", op="ABSOLUTE")
bhor = _node("ShaderNodeMapRange", interp="SMOOTHERSTEP", **{"From Min": 0.0, "From Max": 1.3, "To Min": 1.0, "To Max": 0.0})
BD_Z = _node("ShaderNodeMath", op="ADD")                   # world z = local y + centre z
bup = _node("ShaderNodeMapRange", interp="SMOOTHERSTEP", **{"From Min": -0.1, "From Max": 0.9, "To Min": 0.0, "To Max": 1.0})
bdn = _node("ShaderNodeMapRange", interp="SMOOTHERSTEP", **{"From Min": 1.1, "From Max": 2.6, "To Min": 1.0, "To Max": 0.0})
bm1 = _node("ShaderNodeMath", op="MULTIPLY")
bm2 = _node("ShaderNodeMath", op="MULTIPLY")
BD_S = _node("ShaderNodeMath", op="MULTIPLY")
em = _node("ShaderNodeEmission")
L = bnt.links.new
L(btc.outputs["Object"], bsep.inputs[0])
L(bsep.outputs["X"], babs.inputs[0])
L(babs.outputs[0], bhor.inputs["Value"])
L(bsep.outputs["Y"], BD_Z.inputs[0])
L(BD_Z.outputs[0], bup.inputs["Value"])
L(BD_Z.outputs[0], bdn.inputs["Value"])
L(bhor.outputs["Result"], bm1.inputs[0])
L(bup.outputs["Result"], bm1.inputs[1])
L(bm1.outputs[0], bm2.inputs[0])
L(bdn.outputs["Result"], bm2.inputs[1])
L(bm2.outputs[0], BD_S.inputs[0])
L(BD_S.outputs[0], em.inputs["Strength"])
L(em.outputs["Emission"], bnt.nodes["Material Output"].inputs["Surface"])
BACKDROP.data.materials.append(m_bd)
BACKDROP.visible_glossy = False
BACKDROP.visible_diffuse = False


def backdrop(loc, strength, z0=-0.1, z1=0.9):
    BACKDROP.hide_render = strength <= 0
    BACKDROP.location = loc
    BD_Z.inputs[1].default_value = loc[2]
    BD_S.inputs[1].default_value = strength
    bup.inputs["From Min"].default_value = z0
    bup.inputs["From Max"].default_value = z1


def make_ball(r=0.021335, n_dimples=392, dimple_r=0.00175, depth=0.00024):
    """Golf ball: icosphere with real dimples (Fibonacci-sphere layout)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=7, radius=1.0)
    me = bpy.data.meshes.new("ball")
    bm.to_mesh(me)
    bm.free()
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    i = np.arange(n_dimples) + 0.5
    phi = np.arccos(1 - 2 * i / n_dimples)
    th = math.pi * (1 + 5 ** 0.5) * i
    C = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    best = np.empty(len(V))
    for k in range(0, len(V), 20000):
        best[k:k + 20000] = (V[k:k + 20000] @ C.T).max(1)
    ang = np.arccos(np.clip(best, -1, 1))
    x = np.clip(ang / (dimple_r / r), 0, 1)
    rad = r - depth * np.where(x < 1, 1 - x * x, 0.0)
    me.vertices.foreach_set("co", (V * rad[:, None]).ravel())
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Ball", me)
    sc.collection.objects.link(ob)
    m, _ = mat("Ball_White", (0.86, 0.86, 0.84), 0.3, coat=0.7, coat_rough=0.06)
    me.materials.append(m)
    return ob


BALL = make_ball()
BALL_R = 0.021335

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
               ("top", (0.7, 0.03)), ("sweep", (0.6, 0.025)), ("rake", (0.25, 0.03))):
    add_light(nm, size=sz)
add_light("spot", "SPOT")
# light linking: rims / top / sweep / rake shape the putter only - their reflections on the
# floor turned into bright smears at our grazing camera angles
NO_FLOOR = bpy.data.collections.new("NoFloor")
NO_FLOOR.objects.link(FLOOR)
NO_FLOOR.collection_objects[0].light_linking.link_state = "EXCLUDE"
add_light("keyNF", size=(0.5, 0.5))
for nm in ("rimL", "rimR", "top", "sweep", "rake", "keyNF"):
    LIGHTS[nm].light_linking.receiver_collection = NO_FLOOR
LIGHTS["spot"].data.spot_size = math.radians(34)
LIGHTS["spot"].data.spot_blend = 0.85
LIGHTS["spot"].data.shadow_soft_size = 0.15

cam_data = bpy.data.cameras.new("cam")
cam_data.clip_start = 0.005
cam_data.sensor_width = 36.0
CAM = bpy.data.objects.new("Camera", cam_data)
sc.collection.objects.link(CAM)
sc.camera = CAM


ENERGY = 0.12                      # global light scale (tuned on test stills)


def light(name, loc, target, power, size=None):
    ob = LIGHTS[name]
    power *= ENERGY
    ob.hide_render = power <= 0
    ob.location = loc
    ob.rotation_euler = look_euler(loc, target)
    ob.data.energy = max(power, 0.0)
    if size:
        ob.data.size, ob.data.size_y = size


def camera(loc, target, lens, fstop=None, focus=None, roll=0.0):
    CAM.location = loc
    CAM.rotation_euler = look_euler(loc, target, roll)
    cam_data.lens = lens
    cam_data.dof.use_dof = fstop is not None
    if fstop is not None:
        cam_data.dof.aperture_fstop = fstop
        cam_data.dof.focus_distance = focus if focus else (Vector(target) - Vector(loc)).length


def show(club=True, floor=True, ball=False, club_in_reflections=True):
    for o in CLUB:
        o.hide_render = not club
        o.visible_glossy = club_in_reflections     # the overhead shot: no shaft smear on the floor
    FLOOR.hide_render = not floor
    BALL.hide_render = not ball


# ------------------------------------------------------------------ target line (alignment)
# A thin, softly glowing chalk line on the floor in front of the ball, fading into the dark.
line_me = bpy.data.meshes.new("target_line")
bm = bmesh.new()
_w, _y0, _y1 = 0.0007, -0.046, -3.2
for vx, vy in ((-_w, _y0), (_w, _y0), (_w, _y1), (-_w, _y1)):
    bm.verts.new((vx, vy, 0.0003))
bm.faces.new(bm.verts)
bm.to_mesh(line_me)
bm.free()
LINE = bpy.data.objects.new("TargetLine", line_me)
sc.collection.objects.link(LINE)
m_line = bpy.data.materials.new("TargetLine_Glow")
m_line.use_nodes = True
lnt = m_line.node_tree
for n in list(lnt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        lnt.nodes.remove(n)
l_tc = lnt.nodes.new("ShaderNodeTexCoord")
l_sep = lnt.nodes.new("ShaderNodeSeparateXYZ")
l_fade = lnt.nodes.new("ShaderNodeMapRange")
l_fade.interpolation_type = "SMOOTHERSTEP"
l_fade.inputs["From Min"].default_value = -0.05
l_fade.inputs["From Max"].default_value = -1.6
l_fade.inputs["To Min"].default_value = 1.0
l_fade.inputs["To Max"].default_value = 0.0
LINE_S = lnt.nodes.new("ShaderNodeMath")
LINE_S.operation = "MULTIPLY"
l_em = lnt.nodes.new("ShaderNodeEmission")
l_em.inputs["Color"].default_value = (1.0, 0.98, 0.95, 1)
lnt.links.new(l_tc.outputs["Object"], l_sep.inputs[0])
lnt.links.new(l_sep.outputs["Y"], l_fade.inputs["Value"])
lnt.links.new(l_fade.outputs["Result"], LINE_S.inputs[0])
lnt.links.new(LINE_S.outputs[0], l_em.inputs["Strength"])
lnt.links.new(l_em.outputs["Emission"], lnt.nodes["Material Output"].inputs["Surface"])
LINE.data.materials.append(m_line)
LINE.visible_glossy = False


def target_line(strength):
    LINE.hide_render = strength <= 0
    LINE_S.inputs[1].default_value = strength


# ------------------------------------------------------------------ stroke kinematics
# Pendulum in the stroke plane (shaft line + target line); the pivot sits up the shaft.
AXIS = D_SHAFT.cross(Vector((0, 1, 0))).normalized()    # +angle moves the head toward the target (-Y)
PIVOT = GROUND + D_SHAFT * 1.05
PHI_B = 0.135                                           # backswing / follow-through (rad)
SWING = BAR                                             # top of backswing -> impact (s)
OMEGA = math.pi / (2 * SWING)


def stroke_phi(t, t_imp):
    """Starts at the top of the backswing one bar before impact, holds the finish."""
    x = clamp(t - (t_imp - SWING), 0.0, math.pi / OMEGA)
    return -PHI_B * math.cos(OMEGA * x)


def stroke_matrix(phi):
    R = Matrix.Rotation(phi, 4, AXIS)
    return Matrix.Translation(PIVOT) @ R @ Matrix.Translation(-PIVOT) @ STAND


HEAD_SPEED = PHI_B * OMEGA * (HC - PIVOT).cross(AXIS).length
V0 = 1.6 * HEAD_SPEED               # ball launch speed (slow motion)
DECEL = 0.006                       # rolling resistance (slow motion, m/s^2)
BALL_Y0 = math.tan(math.radians(3.0)) * BALL_R - BALL_R   # touching the lofted face at phi = 0


def ball_state(t, t_imp):
    """Ball centre and roll angle; it rests against the face until impact."""
    d = 0.0
    if t > t_imp:
        dt = min(t - t_imp, V0 / DECEL)
        d = V0 * dt - 0.5 * DECEL * dt * dt
    return Vector((0.0, BALL_Y0 - d, BALL_R + LIFT)), d / BALL_R


def head_at(t, t_imp):
    """World position of the face centre during the stroke."""
    m = Matrix.Translation(PIVOT) @ Matrix.Rotation(stroke_phi(t, t_imp), 4, AXIS) @ Matrix.Translation(-PIVOT)
    return m @ (FACE_C + Vector((0, 0, LIFT)))


def lights_off(*names):
    for n in names:
        light(n, (0, 0, 1), (0, 0, 0), 0)


# ------------------------------------------------------------------ shots
def pose_reveal(t, a, b):
    u = lin(t, a, b)
    show()
    target_line(0)
    ROOT.matrix_world = STAND
    floor_pool(0.0, 0.03, 0.14, 0.45)
    backdrop((0.25, 2.2, 0.35), 0.0)
    camera(vlerp((-0.27, -0.31, 0.042), (-0.175, -0.205, 0.031), ease_io(u)),
           vlerp((0.006, 0.03, 0.022), (0.004, 0.03, 0.017), ease_io(u)), 55, fstop=4.0)
    rim = ease(lin(t, 0.2, 2.2))
    light("rimL", (-0.34, 0.30, 0.13), HC, 70 * rim)
    light("rimR", (0.36, 0.32, 0.16), HC, 55 * rim)
    sx = lerp(-0.40, 0.40, ease_io(lin(t, 1.4, 5.8)))
    light("sweep", (sx, -0.02, 0.32), (sx * 0.25, 0.03, 0.0), 45 * ease(lin(t, 1.0, 2.0)))
    light("key", (-0.28, -0.36, 0.46), HC, 38 * ease(lin(t, 2.6, 6.2)))
    lights_off("top", "fill", "rake", "spot", "keyNF")


def pose_face(t, a, b):
    u = lin(t, a, b)
    show()
    target_line(0)
    ROOT.matrix_world = STAND
    floor_pool(0.0, 0.0, 0.10, 0.30)
    backdrop((0, 2.2, 0.3), 0.0)
    x = lerp(-0.036, 0.030, ease_io(u))           # slow slide from the toe to the GR mark
    loc = Vector((x, -0.135, 0.034))
    camera(loc, (x + 0.004, 0.0, 0.0115), 100, fstop=8.0, focus=0.137)
    light("rake", (-0.30, -0.07, 0.030), FACE_C, 140)
    light("top", (0.02, -0.10, 0.30), FACE_C, 22)
    light("rimR", (0.36, 0.32, 0.16), HC, 40)
    lights_off("key", "fill", "rimL", "spot", "sweep", "keyNF")


def pose_sole(t, a, b):
    u = lin(t, a, b)
    show(club=False, floor=False)
    target_line(0)
    backdrop((0, 2.2, 0.3), 0.0)
    centre = Vector((0.0, 0.0, 0.12))
    spin = math.radians(lerp(-32.0, 6.0, ease_io(u)))
    tilt = math.radians(-105.0)
    hc_m = Vector((0.0, 34.0, 12.5))
    ROOT.matrix_world = (Matrix.Translation(centre) @ Matrix.Rotation(spin, 4, "Z") @ Matrix.Rotation(tilt, 4, "X")
                         @ Matrix.Diagonal((MM, MM, MM, 1.0)) @ Matrix.Translation(-hc_m))
    camera((0.0, -0.30, 0.20 - 0.01 * u), centre + Vector((0, 0, 0.004)), 70, fstop=5.6)
    sx = lerp(-0.45, 0.45, ease_io(lin(t, a + 0.2, b - 0.2)))
    light("sweep", (sx, -0.26, 0.30), centre, 30)
    light("top", (0.0, -0.05, 0.55), centre, 14)
    light("rimL", (-0.30, 0.25, 0.25), centre, 45)
    light("rimR", (0.30, 0.25, 0.20), centre, 45)
    light("fill", (0.25, -0.35, 0.05), centre, 4)
    lights_off("key", "rake", "spot", "keyNF")


def pose_stroke(t, a, b):
    show(ball=True)
    target_line(0)
    floor_pool(0.0, -0.05, 0.16, 0.50)
    backdrop((0, 2.2, 0.3), 0.0)
    ROOT.matrix_world = stroke_matrix(stroke_phi(t, T_IMPACT))
    bc, roll = ball_state(t, T_IMPACT)
    BALL.matrix_world = Matrix.Translation(bc) @ Matrix.Rotation(roll, 4, "X")
    # static low front view through impact, then a slow push toward the held finish
    push = ease_io(lin(t, T_IMPACT + 1.5, b))
    cam = vlerp((0.145, -0.66, 0.062), (0.11, -0.47, 0.050), push)
    face = head_at(t, T_IMPACT)
    tgt = vlerp((0.010, -0.02, 0.022), face + Vector((0.004, 0.0, 0.004)), push)
    d_ball = (bc - cam).length - 0.6 * BALL_R
    d_face = (face - cam).length
    rack = ease(lin(t, T_IMPACT + 1.5, T_IMPACT + 2.4))
    camera(cam, tgt, 85, fstop=5.6, focus=lerp(d_ball, d_face, rack))
    light("key", (0.42, -0.30, 0.95), (0, -0.05, 0.0), 70)
    light("rimL", (-0.40, 0.35, 0.16), HC, 70)
    light("rimR", (0.42, 0.38, 0.18), HC, 55)
    light("top", (0.0, 0.05, 0.42), HC, 10)
    lights_off("fill", "rake", "sweep", "spot", "keyNF")


def pose_center(t, a, b):
    """High toe-side view: the shaft sits in the middle of the head, the head swings
    back and through without turning, and the ball runs straight down the line."""
    u = lin(t, a, b)
    show(ball=True, club_in_reflections=False)
    target_line(0.55 * ease(lin(t, a, a + 1.2)))
    floor_pool(0.0, -0.22, 0.30, 0.85)
    backdrop((0, 2.2, 0.3), 0.0)
    ROOT.matrix_world = stroke_matrix(stroke_phi(t, T_IMPACT2))
    bc, roll = ball_state(t, T_IMPACT2)
    BALL.matrix_world = Matrix.Translation(bc) @ Matrix.Rotation(roll, 4, "X")
    e = ease_io(u)
    cam = vlerp((-0.17, 0.07, 0.50), (-0.17, -0.17, 0.52), e)
    tgt = vlerp((0.0, 0.05, 0.0), (0.0, -0.19, 0.0), e)
    camera(cam, tgt, lerp(46, 38, e), fstop=8.0)
    light("keyNF", (0.10, -0.15, 0.90), (0, -0.15, 0.0), 85, size=(0.9, 0.6))
    light("rimL", (-0.45, 0.45, 0.30), HC, 60)
    light("rimR", (0.45, 0.45, 0.30), HC, 60)
    light("top", (0.0, 0.03, 0.40), HC, 8)
    lights_off("key", "fill", "rake", "sweep", "spot")


def pose_stand(t, a, b):
    """Set down, it stays upright on its own; the camera circles round behind the ball
    to the golfer's view down the line (stepping back to check the alignment)."""
    u = lin(t, a, b)
    show(ball=True)
    target_line(0.5 * ease(lin(t, a + 3.0, a + 5.0)))
    floor_pool(0.05, -0.30, 0.55, 1.60)
    s = t - a                                     # just set down: a tiny damped rock, then still
    rock = math.radians(1.1) * math.exp(-2.6 * s) * math.cos(2 * math.pi * 1.25 * s) if s < 3.0 else 0.0
    pc = Vector((0.0, 0.034, 0.0))
    ROOT.matrix_world = Matrix.Translation(pc) @ Matrix.Rotation(rock, 4, "Y") @ Matrix.Translation(-pc) @ STAND
    BALL.matrix_world = Matrix.Translation((0.0, BALL_Y0 - 0.004, BALL_R + LIFT))
    e = ease_io(u)
    # orbit: low front-left -> round the toe -> behind the putter, rising to eye level
    ang = math.radians(lerp(-116.0, -268.0, e))
    rad = lerp(0.40, 0.82, e)
    o = Vector((0.03, 0.03, 0.0))
    loc = o + Vector((rad * math.cos(ang), rad * math.sin(ang), lerp(0.045, 0.80, e)))
    tgt = vlerp((0.0, 0.034, 0.028), (0.03, -0.14, 0.06), e)
    camera(loc, tgt, lerp(50, 40, e), fstop=lerp(4.0, 11.0, e))
    # the "target": a soft light column far down the line
    backdrop((0.0, -3.4, 0.0), 0.07 * ease(lin(t, a + 2.5, a + 5.5)), z0=-0.25, z1=0.45)
    BACKDROP.rotation_euler = (math.radians(90), 0, 0)
    light("spot", (0.03, -0.05, 1.5), (0.03, -0.05, 0.0), 1800)
    light("rimL", (-0.50, -0.70, 0.70), (0.05, 0.03, 0.40), 100, size=(0.035, 1.6))
    light("rimR", (0.60, -0.65, 0.75), (0.05, 0.03, 0.40), 90, size=(0.035, 1.6))
    light("keyNF", (-0.45, -0.70, 0.55), (0.04, 0.03, 0.12), 110)
    lights_off("key", "fill", "rake", "sweep", "top")


PICK_Y = 0.049                      # ball centre under the cutout arc (model: 49 mm from the face)
PICK_Z_IN = 0.003                   # ball centre 3 mm above the sole once clicked in


def pickup_lift(t):
    """Height of the putter (sole) above the floor during the pick-up."""
    down0, down1 = T_PICK - BAR, T_PICK                 # press down over the ball
    up0, up1 = T_PICK + 0.35, T_PICK + 0.35 + BAR       # pause on the click, then lift
    z_hi, z_in, z_up = 0.060, BALL_R + LIFT - PICK_Z_IN, 0.105
    if t < down1:
        return lerp(z_hi, z_in, ease_io(lin(t, down0, down1)) ** 1.15)
    if t < up0:
        return z_in
    return lerp(z_in, z_up, ease_io(lin(t, up0, up1)))


def pose_pickup(t, a, b):
    u = lin(t, a, b)
    show(ball=True)
    target_line(0)
    floor_pool(0.0, 0.05, 0.18, 0.55)
    backdrop((0, 2.2, 0.3), 0.0)
    z = pickup_lift(t)
    ROOT.matrix_world = Matrix.Translation((0.0, 0.0, z - LIFT)) @ STAND
    if t < T_PICK:                                       # ball waits on the floor
        BALL.matrix_world = Matrix.Translation((0.0, PICK_Y, BALL_R + LIFT))
    else:                                                # ...then travels with the head
        BALL.matrix_world = Matrix.Translation((0.0, PICK_Y, z + PICK_Z_IN))
    e = ease_io(u)
    cam = vlerp((0.21, 0.40, 0.070), (0.17, 0.33, 0.120), e)
    tgt = Vector((0.0, 0.045, max(0.040, z + 0.004)))
    camera(cam, tgt, 60, fstop=5.6)
    light("keyNF", (0.35, 0.45, 0.55), (0, 0.04, 0.05), 70)
    light("rimL", (-0.45, -0.10, 0.25), (0, 0.04, 0.05), 60)
    light("rimR", (0.40, -0.25, 0.30), (0, 0.04, 0.05), 50)
    light("top", (0.0, 0.10, 0.50), (0, 0.04, 0.05), 10)
    lights_off("key", "fill", "rake", "sweep", "spot")


POSES = {"reveal": pose_reveal, "face": pose_face, "sole": pose_sole, "stroke": pose_stroke,
         "center": pose_center, "stand": pose_stand, "pickup": pose_pickup}

DEFAULT_RIM = (0.9, 0.035)


def pose(t):
    name, a, b = shot_at(t)
    for nm in ("rimL", "rimR"):
        LIGHTS[nm].data.size, LIGHTS[nm].data.size_y = DEFAULT_RIM
    POSES[name](t, a, b)
    return name


# ------------------------------------------------------------------ render settings
QUALITY = {
    "preview": dict(res=(960, 540), samples=12, threshold=0.06),
    "probe": dict(res=(960, 540), samples=1, threshold=0.5),
    "draft": dict(res=(1920, 1080), samples=24, threshold=0.04),
    "final": dict(res=(1920, 1080), samples=24, threshold=0.04),     # = draft; OIDN makes 48 spp identical
}


def setup_render(q):
    c = QUALITY[q]
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = c["res"]
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
    cy.denoising_quality = "BALANCED"          # same look as HIGH here, ~15% faster per frame
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
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    setup_render(a.quality)
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
