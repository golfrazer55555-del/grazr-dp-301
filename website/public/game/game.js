/* GRAZR putting: a screen-golf style putting green with the GRAZR DP-301 putter.
   Units: metres, seconds. three.js world: Y up, the green lies in X/Z. */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const $ = (s) => document.querySelector(s);
const ui = {
  loading: $("[data-loading]"), bar: $("[data-loading-bar]"),
  hole: $("[data-hole]"), strokes: $("[data-strokes]"), dist: $("[data-dist]"), elev: $("[data-elev]"),
  elevLabel: $("[data-elev-label]"), speed: $("[data-speed]"), power: $("[data-power]"), powerBox: $("[data-power-box]"),
  powerFill: $("[data-power-fill]"), hint: $("[data-hint]"), toast: $("[data-toast]"), result: $("[data-result]"),
  resultTitle: $("[data-result-title]"), resultSub: $("[data-result-sub]"), view: $("[data-view]"),
};

/* ------------------------------------------------------------------ constants */
const G = 9.81;
const BALL_R = 0.02135;           // golf ball 42.7 mm
const CUP_R = 0.054;              // cup 108 mm
const CUP_DEPTH = 0.10;
const STIMP = 3.0;                // green speed (m): a ball released at 1.83 m/s rolls this far on the flat
const DEC = 1.83 * 1.83 / (2 * STIMP);   // rolling resistance on the green (m/s^2)
const OK_R = 0.5;                 // concede ("OK") inside this distance
const MAX_D = 20;                 // strongest putt, as flat roll distance (m)
const ROLL = 5 / 7;               // rolling sphere: share of the slope force that accelerates the ball

/* ------------------------------------------------------------------ hole: seeded slopes */
function rng(seed) {
  let a = seed >>> 0;
  return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

let hole;
function makeHole(n) {
  const r = rng(n * 7919 + 17);
  const D = 3.5 + r() * 8.5;
  const th = r() * Math.PI * 2;
  const start = new THREE.Vector2(Math.cos(th) * D, Math.sin(th) * D);
  const cup = new THREE.Vector2(0, 0);
  const tilt = 0.006 + r() * 0.014, tdir = r() * Math.PI * 2;
  const bumps = [];
  const perp = new THREE.Vector2(-Math.sin(th), Math.cos(th));
  for (let i = 0; i < 3; i++) {
    const t = 0.15 + r() * 0.7;
    const p = cup.clone().lerp(start, t).addScaledVector(perp, (r() - 0.5) * 5);
    bumps.push({ x: p.x, z: p.y, a: (r() - 0.5) * 0.24, s: 1.8 + r() * 3.2 });
  }
  const h = { n, D, start, cup, tx: Math.cos(tdir) * tilt, tz: Math.sin(tdir) * tilt, bumps,
    gc: cup.clone().lerp(start, 0.5), gr: D / 2 + 4.2 + r() * 1.5, wob: r() * 6.28 };
  // keep the cup on a playable slope (< 2.5 %)
  for (let k = 0; k < 12; k++) {
    const g = gradAt(h, 0, 0);
    if (Math.hypot(g.x, g.y) < 0.025) break;
    h.tx *= 0.8; h.tz *= 0.8; h.bumps.forEach((b) => (b.a *= 0.8));
  }
  return h;
}
function heightAt(h, x, z) {
  let y = h.tx * x + h.tz * z;
  for (const b of h.bumps) y += b.a * Math.exp(-((x - b.x) ** 2 + (z - b.z) ** 2) / (2 * b.s * b.s));
  return y;
}
function gradAt(h, x, z) {
  let gx = h.tx, gz = h.tz;
  for (const b of h.bumps) {
    const e = b.a * Math.exp(-((x - b.x) ** 2 + (z - b.z) ** 2) / (2 * b.s * b.s)) / (b.s * b.s);
    gx -= e * (x - b.x); gz -= e * (z - b.z);
  }
  return new THREE.Vector2(gx, gz);
}
// 0 inside the green, 1 on the fringe, 2 in the rough (same formula as the ground shader)
function edgeAt(h, x, z) {
  const dx = x - h.gc.x, dz = z - h.gc.y;
  const a = Math.atan2(dz, dx);
  return Math.hypot(dx, dz) / (h.gr * (1 + 0.07 * Math.sin(3 * a + h.wob) + 0.04 * Math.sin(5 * a + 1.7 * h.wob)));
}
const H = (x, z) => heightAt(hole, x, z);

/* ------------------------------------------------------------------ renderer, scene */
const canvas = $("[data-canvas]");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.92;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xcfe3ef, 35, 140);
const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 400);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

// sky dome
{
  const sky = new THREE.Mesh(new THREE.SphereGeometry(300, 32, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { top: { value: new THREE.Color(0x5d97cf) }, mid: { value: new THREE.Color(0xa9cbe6) }, hor: { value: new THREE.Color(0xe4eef3) } },
    vertexShader: "varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }",
    fragmentShader: "uniform vec3 top, mid, hor; varying vec3 vP; void main(){ float y = max(vP.y, 0.); vec3 c = mix(hor, mid, smoothstep(0., .12, y)); c = mix(c, top, smoothstep(.12, .6, y)); gl_FragColor = vec4(c, 1.); }",
  }));
  scene.add(sky);
}
scene.add(new THREE.HemisphereLight(0xdfeeff, 0x2d4a1c, 0.55));
const sun = new THREE.DirectionalLight(0xfff4e0, 1.9);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4, near: 0.5, far: 30 });
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.01;
scene.add(sun, sun.target);
const SUN_DIR = new THREE.Vector3(-0.45, 0.8, 0.38).normalize();

/* ------------------------------------------------------------------ ground (green, fringe, rough) */
const groundU = {
  uCup: { value: new THREE.Vector2() }, uGc: { value: new THREE.Vector2() }, uGr: { value: 10 }, uWob: { value: 0 },
  uOk: { value: OK_R },
};
const groundMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.92, metalness: 0, envMapIntensity: 0.25 });
groundMat.onBeforeCompile = (sh) => {
  Object.assign(sh.uniforms, groundU);
  sh.vertexShader = sh.vertexShader
    .replace("#include <common>", "#include <common>\nvarying vec3 vWP;")
    .replace("#include <begin_vertex>", "#include <begin_vertex>\nvWP = (modelMatrix * vec4(transformed, 1.0)).xyz;");
  sh.fragmentShader = sh.fragmentShader
    .replace("#include <common>", `#include <common>
      varying vec3 vWP; uniform vec2 uCup, uGc; uniform float uGr, uWob, uOk;
      float gline(float v){ float d = abs(fract(v + .5) - .5); float w = fwidth(v); return (1. - smoothstep(w * .5, w * 1.5, d)) * (1. - smoothstep(.015, .06, w)); }`)
    .replace("#include <color_fragment>", `#include <color_fragment>
      vec2 q = vWP.xz - uGc; float a = atan(q.y, q.x);
      float e = length(q) / (uGr * (1. + .07 * sin(3. * a + uWob) + .04 * sin(5. * a + 1.7 * uWob)));
      float dc = distance(vWP.xz, uCup);
      if (dc < ${CUP_R.toFixed(4)}) discard;
      vec3 green = vec3(.075, .25, .035), fringe = vec3(.05, .17, .022), rough = vec3(.028, .09, .012);
      float stripe = step(.5, fract(dot(vWP.xz, vec2(.8, .6)) / 2.4));
      green *= mix(.9, 1.1, stripe);
      vec3 c = e < 1. ? green : (e < 1.09 ? fringe : rough);
      float onGreen = 1. - smoothstep(.985, 1., e);
      c = mix(c, vec3(.8), .13 * max(gline(vWP.x), gline(vWP.z)) * onGreen);
      c = mix(c, vec3(1.), .32 * (1. - smoothstep(.006, .014, abs(dc - uOk))));
      diffuseColor.rgb = c;`);
};
let ground;
function buildGround() {
  if (ground) { scene.remove(ground); ground.geometry.dispose(); }
  const size = 90, seg = 360;
  const geo = new THREE.PlaneGeometry(size, size, seg, seg);
  geo.rotateX(-Math.PI / 2);
  geo.translate(hole.gc.x, 0, hole.gc.y);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) p.setY(i, H(p.getX(i), p.getZ(i)));
  geo.computeVertexNormals();
  ground = new THREE.Mesh(geo, groundMat);
  ground.receiveShadow = true;
  scene.add(ground);
  groundU.uCup.value.copy(hole.cup); groundU.uGc.value.copy(hole.gc); groundU.uGr.value = hole.gr; groundU.uWob.value = hole.wob;
}

/* ------------------------------------------------------------------ slope dots (flow downhill) */
const dotU = { uTime: { value: 0 }, uScale: { value: 800 } };
const dotMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, uniforms: dotU,
  vertexShader: `attribute vec2 aDir; attribute float aSlope, aPhase; uniform float uTime, uScale; varying float vA;
    void main(){ float t = fract(uTime * (.12 + aSlope * 14.) + aPhase); vec3 p = position;
      p.xz += aDir * (t - .5) * .42; p.y += -aSlope * (t - .5) * .42 + .02;
      vA = sin(t * 3.14159) * clamp(aSlope * 70., .25, 1.);
      vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv;
      gl_PointSize = clamp(uScale * .045 / -mv.z, 2., 11.); }`,
  fragmentShader: `varying float vA; void main(){ vec2 c = gl_PointCoord - .5; if (dot(c, c) > .25) discard; gl_FragColor = vec4(1., 1., 1., vA * .8); }`,
});
let dots;
function buildDots() {
  if (dots) { scene.remove(dots); dots.geometry.dispose(); }
  const pos = [], dir = [], slope = [], phase = [];
  const step = 0.5, R = hole.gr * 1.15;
  for (let x = hole.gc.x - R; x <= hole.gc.x + R; x += step) {
    for (let z = hole.gc.y - R; z <= hole.gc.y + R; z += step) {
      const gx = Math.round(x / step) * step, gz = Math.round(z / step) * step;
      if (edgeAt(hole, gx, gz) > 0.98) continue;
      const g = gradAt(hole, gx, gz), m = Math.hypot(g.x, g.y);
      pos.push(gx, H(gx, gz), gz);
      dir.push(m > 1e-5 ? -g.x / m : 0, m > 1e-5 ? -g.y / m : 0);
      slope.push(m);
      phase.push(Math.random());
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("aDir", new THREE.Float32BufferAttribute(dir, 2));
  geo.setAttribute("aSlope", new THREE.Float32BufferAttribute(slope, 1));
  geo.setAttribute("aPhase", new THREE.Float32BufferAttribute(phase, 1));
  dots = new THREE.Points(geo, dotMat);
  dots.frustumCulled = false;
  scene.add(dots);
}

/* ------------------------------------------------------------------ cup, pin, flag */
const cupGroup = new THREE.Group();
{
  const liner = new THREE.Mesh(new THREE.CylinderGeometry(CUP_R, CUP_R, 0.022, 48, 1, true),
    new THREE.MeshStandardMaterial({ color: 0xf2f2f2, roughness: 0.6, side: THREE.BackSide }));
  liner.position.y = -0.011 - 0.003;
  const wall = new THREE.Mesh(new THREE.CylinderGeometry(CUP_R, CUP_R, CUP_DEPTH, 48, 1, true),
    new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 1, side: THREE.BackSide }));
  wall.position.y = -CUP_DEPTH / 2 - 0.02;
  const bottom = new THREE.Mesh(new THREE.CircleGeometry(CUP_R, 48), new THREE.MeshStandardMaterial({ color: 0x0c0c0c, roughness: 1 }));
  bottom.rotation.x = -Math.PI / 2; bottom.position.y = -CUP_DEPTH - 0.02;
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 2.15, 12), new THREE.MeshStandardMaterial({ color: 0xf5f5f5, roughness: 0.4 }));
  pole.position.y = 2.15 / 2 - CUP_DEPTH; pole.castShadow = true;
  cupGroup.add(liner, wall, bottom, pole);
  // flag: black with the GRAZR mark
  const c = document.createElement("canvas"); c.width = 512; c.height = 340;
  const g = c.getContext("2d"); g.fillStyle = "#0b0b0b"; g.fillRect(0, 0, 512, 340);
  g.strokeStyle = "#c9a35c"; g.lineWidth = 10; g.strokeRect(14, 14, 484, 312);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const logo = new Image(); logo.onload = () => { const s = 220 / logo.height; g.drawImage(logo, 256 - logo.width * s / 2, 60, logo.width * s, 220); tex.needsUpdate = true; };
  logo.src = "/assets/img/logo-stacked.png";
  const flagGeo = new THREE.PlaneGeometry(0.52, 0.345, 16, 4); flagGeo.translate(0.26, 0, 0);
  const flag = new THREE.Mesh(flagGeo, new THREE.MeshStandardMaterial({ map: tex, side: THREE.DoubleSide, roughness: 0.8 }));
  flag.position.set(0.011, 2.15 - CUP_DEPTH - 0.19, 0); flag.castShadow = true;
  cupGroup.add(flag);
  cupGroup.userData.flag = flag;
  cupGroup.userData.fadeMats = [pole.material, flag.material];
}
scene.add(cupGroup);
function waveFlag(t) {
  const f = cupGroup.userData.flag, p = f.geometry.attributes.position;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i); p.setZ(i, Math.sin(x * 9 - t * 3.2) * 0.025 * (x / 0.52)); }
  p.needsUpdate = true;
}

/* ------------------------------------------------------------------ trees around the course */
{
  const trunk = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.18, 0.25, 2.2, 6), new THREE.MeshStandardMaterial({ color: 0x4a3524, roughness: 1 }), 90);
  const crown = new THREE.InstancedMesh(new THREE.ConeGeometry(2.2, 6.5, 8), new THREE.MeshStandardMaterial({ color: 0x1f4a1f, roughness: 1 }), 90);
  const m = new THREE.Matrix4(), r = rng(99);
  for (let i = 0; i < 90; i++) {
    const a = r() * Math.PI * 2, d = 30 + r() * 26, s = 0.7 + r() * 0.8;
    const x = Math.cos(a) * d, z = Math.sin(a) * d;
    m.makeScale(s, s, s).setPosition(x, 1.1 * s - 0.3, z); trunk.setMatrixAt(i, m);
    m.makeScale(s, s, s).setPosition(x, (2.2 + 3.25) * s - 0.6, z); crown.setMatrixAt(i, m);
  }
  scene.add(trunk, crown);
  scene.userData.trees = [trunk, crown];
}

/* ------------------------------------------------------------------ ball */
const ballTex = (() => {
  const c = document.createElement("canvas"); c.width = c.height = 256; const g = c.getContext("2d");
  g.fillStyle = "#f6f6f4"; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 600; i++) { g.fillStyle = `rgba(0,0,0,${0.04 + Math.random() * 0.04})`; g.beginPath();
    g.arc(Math.random() * 256, Math.random() * 256, 3 + Math.random() * 2, 0, 7); g.fill(); }
  g.fillStyle = "#111"; g.fillRect(0, 124, 256, 8);       // alignment line, shows the roll
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
})();
const ball = new THREE.Mesh(new THREE.SphereGeometry(BALL_R, 40, 24), new THREE.MeshStandardMaterial({ map: ballTex, roughness: 0.35, envMapIntensity: 0.6 }));
ball.castShadow = true;
scene.add(ball);

/* ------------------------------------------------------------------ top-view markers (ball and cup read at any height) */
function marker(color, r) {
  const m = new THREE.Mesh(new THREE.RingGeometry(r * 0.62, r, 40), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.95, depthTest: false }));
  m.rotation.x = -Math.PI / 2; m.renderOrder = 10; m.visible = false; scene.add(m); return m;
}
const mkBall = marker(0xffffff, 1), mkCup = marker(0xffd166, 1);
function updateMarkers() {
  const on = st.top;
  mkBall.visible = mkCup.visible = on;
  if (!on) return;
  const s = camera.position.distanceTo(ball.position) * 0.018;
  mkBall.position.set(ball.position.x, ball.position.y + 0.02, ball.position.z); mkBall.scale.setScalar(s);
  mkCup.position.copy(cupGroup.position).add(new THREE.Vector3(0, 0.02, 0)); mkCup.scale.setScalar(s * 1.4);
}

/* ------------------------------------------------------------------ aim line */
const aimMat = new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: 0.12, gapSize: 0.08, transparent: true, opacity: 0.85 });
const aimLine = new THREE.Line(new THREE.BufferGeometry(), aimMat);
scene.add(aimLine);
function updateAimLine() {
  const pts = [], len = st.top ? Math.max(3.2, hole.cup.distanceTo(st.pos) * 1.1) : 3.2;
  for (let i = 0; i <= 40; i++) {
    const d = 0.08 + (len * i) / 40, x = st.pos.x + st.aim.x * d, z = st.pos.y + st.aim.y * d;
    pts.push(new THREE.Vector3(x, H(x, z) + 0.004, z));
  }
  aimLine.geometry.dispose();
  aimLine.geometry = new THREE.BufferGeometry().setFromPoints(pts);
  aimLine.computeLineDistances();
}

/* ------------------------------------------------------------------ the putter (DP-301) */
const putter = { root: new THREE.Group(), pivot: new THREE.Group(), model: null, angle: 0 };
putter.root.add(putter.pivot);
scene.add(putter.root);
// model space (mm, Y up): face plane z = 0 facing +Z, sole y = 0, toe-heel along X, grip top near (232, 832, -7)
const PIVOT_MM = new THREE.Vector3(232, 832, -7);
function loadPutter(onProgress) {
  return new Promise((resolve) => {
    new GLTFLoader().load("/media/3d/dp301.glb", (gltf) => {
      const m = gltf.scene;
      m.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      m.position.copy(PIVOT_MM).multiplyScalar(-0.001);
      putter.pivot.position.copy(PIVOT_MM).multiplyScalar(0.001);
      putter.pivot.add(m);
      putter.model = m;
      resolve();
    }, (e) => { if (e.total) onProgress(e.loaded / e.total); }, () => resolve());
  });
}
function placePutter() {
  // address: face square to the aim line, touching the back of the ball
  const x = st.pos.x - st.aim.x * BALL_R, z = st.pos.y - st.aim.y * BALL_R;
  putter.root.position.set(x, H(x, z), z);
  putter.root.rotation.set(0, Math.atan2(st.aim.x, st.aim.y), 0);
  setSwing(0);
}
function setSwing(a) { putter.angle = a; putter.pivot.rotation.x = a; }
const ARM = 0.86;                                   // pivot to head, m
const backswingFor = (d) => (0.04 + 0.024 * d) / ARM;   // radians of backswing for a flat roll of d metres

/* ------------------------------------------------------------------ sound */
let actx, hitBuf;
function audio() {
  if (!actx) {
    actx = new (window.AudioContext || window.webkitAudioContext)();
    fetch("/game/hit.mp3").then((r) => r.arrayBuffer()).then((b) => actx.decodeAudioData(b)).then((d) => (hitBuf = d)).catch(() => {});
  }
  if (actx.state === "suspended") actx.resume();
  return actx;
}
function playHit(v) {
  if (!actx || !hitBuf) return;
  const s = actx.createBufferSource(), g = actx.createGain();
  s.buffer = hitBuf; g.gain.value = Math.min(1, 0.3 + v / 3.5); s.connect(g).connect(actx.destination); s.start();
}
function playCup() {
  if (!actx) return;
  const t = actx.currentTime;
  [0, 0.11].forEach((dt, i) => {
    const o = actx.createOscillator(), g = actx.createGain();
    o.type = "triangle"; o.frequency.setValueAtTime(i ? 520 : 380, t + dt); o.frequency.exponentialRampToValueAtTime(i ? 300 : 160, t + dt + 0.12);
    g.gain.setValueAtTime(0.0001, t + dt); g.gain.exponentialRampToValueAtTime(i ? 0.18 : 0.35, t + dt + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dt + 0.22);
    o.connect(g).connect(actx.destination); o.start(t + dt); o.stop(t + dt + 0.25);
  });
}

/* ------------------------------------------------------------------ game state */
const st = {
  pos: new THREE.Vector2(), vel: new THREE.Vector2(), aim: new THREE.Vector2(0, 1), power: 3, strokes: 0,
  mode: "aim",                // aim | swing | roll | drop | done
  swingT: 0, swingFrom: 0, launched: false, overCup: false, dropT: 0, dropFrom: new THREE.Vector3(),
  spin: new THREE.Quaternion(), top: false, camPos: new THREE.Vector3(), camLook: new THREE.Vector3(), follow: new THREE.Vector2(0, 1),
};
let holeNo = 1;

function startHole(n) {
  holeNo = n;
  hole = makeHole(n);
  buildGround(); buildDots();
  cupGroup.position.set(hole.cup.x, H(hole.cup.x, hole.cup.y), hole.cup.y);
  st.pos.copy(hole.start); st.vel.set(0, 0); st.strokes = 0; st.top = false;
  st.spin.identity(); ball.quaternion.identity();
  ui.result.hidden = true;
  readyToPutt(true);
  snapCamera();
  if (window.gtag) window.gtag("event", "putting_game_hole_start", { hole: n });
}
function readyToPutt(first) {
  st.mode = "aim";
  st.aim.copy(hole.cup).sub(st.pos).normalize();
  const d = hole.cup.distanceTo(st.pos);
  if (first || st.power > d * 1.6 || st.power < d * 0.6) st.power = Math.min(MAX_D, Math.round(d * 10) / 10);
  ball.position.set(st.pos.x, H(st.pos.x, st.pos.y) + BALL_R, st.pos.y);
  ball.visible = true; aimLine.visible = true; putter.root.visible = true;
  placePutter(); updateAimLine(); hud();
  ui.hint.hidden = false;
}

function hud() {
  const d = hole.cup.distanceTo(st.pos);
  const dh = H(hole.cup.x, hole.cup.y) - H(st.pos.x, st.pos.y);
  ui.hole.textContent = `연습 그린 ${holeNo}번`;
  ui.strokes.textContent = `${st.strokes}타`;
  ui.dist.textContent = d.toFixed(2);
  ui.elev.textContent = Math.abs(dh).toFixed(2);
  ui.elevLabel.textContent = Math.abs(dh) < 0.005 ? "평지" : dh > 0 ? "오르막" : "내리막";
  ui.elevLabel.dataset.dir = Math.abs(dh) < 0.005 ? "flat" : dh > 0 ? "up" : "down";
  ui.speed.textContent = STIMP.toFixed(1);
  ui.power.textContent = st.power.toFixed(1);
  ui.powerFill.style.transform = `scaleX(${st.power / MAX_D})`;
}

function toast(text, ms = 1400) {
  ui.toast.textContent = text; ui.toast.hidden = false; ui.toast.classList.remove("is-on");
  void ui.toast.offsetWidth; ui.toast.classList.add("is-on");
  clearTimeout(toast.t); toast.t = setTimeout(() => (ui.toast.hidden = true), ms);
}

/* ------------------------------------------------------------------ putting */
function putt() {
  if (st.mode !== "aim") return;
  audio();
  st.mode = "swing"; st.swingT = 0; st.swingFrom = backswingFor(st.power); st.launched = false;
  aimLine.visible = false; ui.hint.hidden = true;
  if (window.gtag) window.gtag("event", "putting_game_putt", { hole: holeNo, power: st.power });
}
function launch() {
  const v0 = Math.sqrt(2 * DEC * st.power);
  st.vel.copy(st.aim).multiplyScalar(v0);
  st.strokes++; st.follow.copy(st.aim); st.overCup = false;
  playHit(v0); hud();
  st.mode = "roll";
}
const SWING_BACK_HOLD = 0.12, SWING_DOWN = 0.32, SWING_THRU = 0.28;
function swingStep(dt) {
  st.swingT += dt;
  const t = st.swingT, b = st.swingFrom;
  if (t < SWING_BACK_HOLD) setSwing(b);
  else if (t < SWING_BACK_HOLD + SWING_DOWN) {
    const u = (t - SWING_BACK_HOLD) / SWING_DOWN;
    setSwing(b * (1 - u * u));                  // accelerating through the ball
  } else {
    if (!st.launched) { st.launched = true; launch(); }
    const u = Math.min(1, (t - SWING_BACK_HOLD - SWING_DOWN) / SWING_THRU);
    setSwing(-b * 0.85 * Math.sin(u * Math.PI / 2));
  }
}

function physicsStep(dt) {
  const p = st.pos, v = st.vel;
  const g = gradAt(hole, p.x, p.y);
  const e = edgeAt(hole, p.x, p.y);
  const dec = DEC * (e < 1 ? 1 : e < 1.09 ? 2.6 : 7);
  const ax = -ROLL * G * g.x, az = -ROLL * G * g.y;
  const sp = v.length();
  if (sp < 0.012) {
    // at rest unless the slope beats rolling resistance
    if (Math.hypot(ax, az) < dec) { v.set(0, 0); return true; }
  }
  v.x += ax * dt; v.y += az * dt;
  const s2 = v.length();
  if (s2 > 0) { const nd = Math.max(0, s2 - dec * dt); v.multiplyScalar(nd / s2); }
  p.addScaledVector(v, dt);
  // cup
  const toC = new THREE.Vector2().subVectors(hole.cup, p), dc = toC.length();
  if (dc < CUP_R) {
    if (!st.overCup) {
      st.overCup = true;
      const vs = v.length(), vd = v.clone().normalize();
      const b = Math.abs(vd.x * toC.y - vd.y * toC.x);                 // miss distance of the path
      const vmax = 1.55 * Math.sqrt(Math.max(0, 1 - (b / CUP_R) ** 2)) + 0.12;
      if (vs <= vmax) { startDrop(); return false; }
      // too fast: rides the lip, loses speed and is turned away from the centre
      const side = Math.sign(vd.x * toC.y - vd.y * toC.x) || 1;
      v.rotateAround(new THREE.Vector2(), -side * 0.5 * (b / CUP_R) * Math.min(1, 1.6 / vs)).multiplyScalar(0.78);
    } else if (v.length() < 0.25) { startDrop(); return false; }
  } else if (dc > CUP_R + BALL_R) st.overCup = false;
  if (e > 2.2) { v.set(0, 0); return true; }
  return false;
}
function startDrop() {
  st.mode = "drop"; st.dropT = 0; st.dropFrom.copy(ball.position);
  playCup();
}

/* ------------------------------------------------------------------ results */
function finishHole(kind) {
  st.mode = "done";
  const n = st.strokes + (kind === "ok" ? 1 : 0);
  const names = { 1: "원 퍼트", 2: "투 퍼트", 3: "쓰리 퍼트" };
  ui.resultTitle.textContent = kind === "ok" ? `OK · ${names[n] || n + " 퍼트"}` : (n === 1 ? "원 퍼트 홀인!" : `홀인 · ${names[n] || n + " 퍼트"}`);
  ui.resultSub.textContent = `연습 그린 ${holeNo}번 · ${hole.D.toFixed(1)}m · ${n}타`;
  setTimeout(() => (ui.result.hidden = false), kind === "ok" ? 900 : 1300);
  if (window.gtag) window.gtag("event", "putting_game_hole_done", { hole: holeNo, strokes: n, ok: kind === "ok" });
}
function ballStopped() {
  const d = hole.cup.distanceTo(st.pos);
  if (d <= OK_R) { toast("OK", 1200); finishHole("ok"); return; }
  setTimeout(() => { readyToPutt(false); }, 700);
}

/* ------------------------------------------------------------------ camera */
const UP = new THREE.Vector3(0, 1, 0);
function cameraTarget(out) {
  const bp = new THREE.Vector3(st.pos.x, H(st.pos.x, st.pos.y), st.pos.y);
  if (st.top) {
    const c = new THREE.Vector3(hole.cup.x, H(hole.cup.x, hole.cup.y), hole.cup.y);
    // straight down over the middle, high enough that ball and cup clear the HUD panels
    const mid = bp.clone().lerp(c, 0.5), span = Math.max(3, bp.distanceTo(c));
    const half = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const need = Math.max((span / 2 + 1.2) / (half * 0.62), (span / 2 + 1.2) / (half * camera.aspect * 0.9) * 0.4);
    out.pos.copy(mid).add(new THREE.Vector3(st.aim.x * 0.001, need, st.aim.y * 0.001));
    out.look.copy(mid);
    return;
  }
  if (st.mode === "roll" || st.mode === "drop" || st.mode === "done") {
    const f = new THREE.Vector3(st.follow.x, 0, st.follow.y);
    const near = hole.cup.distanceTo(st.pos) < 1.2 || st.mode !== "roll";
    out.pos.copy(bp).addScaledVector(f, near ? -1.1 : -2.3).add(new THREE.Vector3(0, near ? 0.55 : 0.95, 0));
    out.look.copy(bp).addScaledVector(f, near ? 0.25 : 1.4);
    return;
  }
  const f = new THREE.Vector3(st.aim.x, 0, st.aim.y), right = new THREE.Vector3(-st.aim.y, 0, st.aim.x);
  out.pos.copy(bp).addScaledVector(f, -2.4).addScaledVector(right, 0.55).add(new THREE.Vector3(0, 1.22, 0));
  out.look.copy(bp).addScaledVector(f, 2.8).addScaledVector(right, 0.12);
}
const camT = { pos: new THREE.Vector3(), look: new THREE.Vector3() };
function snapCamera() { cameraTarget(camT); st.camPos.copy(camT.pos); st.camLook.copy(camT.look); applyCamera(); }
function applyCamera() {
  camera.position.copy(st.camPos);
  camera.up.copy(st.top ? new THREE.Vector3(st.aim.x, 0, st.aim.y) : UP);
  camera.lookAt(st.camLook);
}

/* ------------------------------------------------------------------ input */
const drag = { on: false, x: 0, y: 0, kind: null, p0: 0, a0: 0 };
function setAim(angle) { st.aim.set(Math.sin(angle), Math.cos(angle)); placePutter(); updateAimLine(); }
const aimAngle = () => Math.atan2(st.aim.x, st.aim.y);
function setPower(d) {
  st.power = Math.max(0.3, Math.min(MAX_D, Math.round(d * 10) / 10));
  if (st.mode === "aim") setSwing(backswingFor(st.power) * (drag.kind === "power" ? 1 : 0));
  hud();
}
canvas.addEventListener("pointerdown", (e) => {
  audio();
  if (st.mode !== "aim") return;
  canvas.setPointerCapture(e.pointerId);
  Object.assign(drag, { on: true, x: e.clientX, y: e.clientY, kind: null, p0: st.power, a0: aimAngle() });
});
canvas.addEventListener("pointermove", (e) => {
  if (!drag.on || st.mode !== "aim") return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (!drag.kind && Math.hypot(dx, dy) > 10) drag.kind = Math.abs(dy) > Math.abs(dx) ? "power" : "aim";
  if (drag.kind === "aim") {
    setAim(drag.a0 - dx * (st.top ? 0.004 : 0.0025));
  } else if (drag.kind === "power") {
    // pull down from where the finger started: the backswing; the further, the stronger
    const span = Math.min(window.innerHeight * 0.42, 340);
    const u = Math.max(0, dy) / span;
    setPower(MAX_D * Math.min(1, u) ** 1.5);
    ui.powerBox.classList.add("is-active");
  }
});
function endDrag(e) {
  if (!drag.on) return;
  drag.on = false;
  ui.powerBox.classList.remove("is-active");
  if (drag.kind === "power" && st.mode === "aim") {
    const dy = e.clientY - drag.y;
    if (dy > 14) putt(); else { setPower(drag.p0); setSwing(0); }
  }
  drag.kind = null;
}
canvas.addEventListener("pointerup", endDrag);
canvas.addEventListener("pointercancel", (e) => { drag.on = false; drag.kind = null; setSwing(0); });
document.querySelectorAll("[data-aim]").forEach((b) => b.addEventListener("click", () => {
  audio(); if (st.mode === "aim") setAim(aimAngle() + parseFloat(b.dataset.aim) * Math.PI / 180);
}));
document.querySelectorAll("[data-pow]").forEach((b) => b.addEventListener("click", () => { audio(); if (st.mode === "aim") setPower(st.power + parseFloat(b.dataset.pow)); }));
$("[data-putt]").addEventListener("click", () => putt());
ui.view.addEventListener("click", () => { st.top = !st.top; ui.view.textContent = st.top ? "볼 보기" : "그린 보기"; if (st.mode === "aim") updateAimLine(); });
$("[data-retry]").addEventListener("click", () => startHole(holeNo));
$("[data-next]").addEventListener("click", () => startHole(holeNo + 1));
window.addEventListener("keydown", (e) => {
  if (st.mode !== "aim") return;
  const fine = e.shiftKey ? 0.1 : 0.5;
  if (e.key === "ArrowLeft") setAim(aimAngle() + fine * Math.PI / 180);
  else if (e.key === "ArrowRight") setAim(aimAngle() - fine * Math.PI / 180);
  else if (e.key === "ArrowUp") setPower(st.power + (e.shiftKey ? 0.1 : 0.5));
  else if (e.key === "ArrowDown") setPower(st.power - (e.shiftKey ? 0.1 : 0.5));
  else if (e.key === " " || e.key === "Enter") { e.preventDefault(); putt(); }
  else return;
  audio();
});

/* ------------------------------------------------------------------ loop */
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.fov = w / h < 0.8 ? 58 : 42;
  camera.updateProjectionMatrix();
  dotU.uScale.value = h * renderer.getPixelRatio();
}
window.addEventListener("resize", resize);

let last = performance.now(), acc = 0, clock = 0;
const STEP = 1 / 240;
const SIDE_CAM = new URLSearchParams(location.search).get("cam") === "side";
const SIM = Math.min(8, parseFloat(new URLSearchParams(location.search).get("sim")) || 1);   // test speed-up
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now; clock += dt;
  if (st.mode === "swing") swingStep(dt);
  if (st.mode === "roll") {
    const dtr = dt * SIM;
    if (putter.angle < 0) setSwing(Math.min(0, putter.angle + dt * 0.8));
    acc += dtr;
    let stopped = false;
    while (acc >= STEP && st.mode === "roll") { acc -= STEP; stopped = physicsStep(STEP); if (stopped) break; }
    const sp = st.vel.length();
    if (sp > 0.05) st.follow.lerp(st.vel.clone().normalize(), 1 - Math.exp(-dt * 2.5)).normalize();
    const y = H(st.pos.x, st.pos.y) + BALL_R;
    ball.position.set(st.pos.x, y, st.pos.y);
    if (sp > 1e-4) {
      const axis = new THREE.Vector3(st.vel.y, 0, -st.vel.x).normalize();
      ball.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(axis, (sp * dt) / BALL_R));
    }
    if (st.mode === "roll") {
      ui.dist.textContent = hole.cup.distanceTo(st.pos).toFixed(2);
      if (stopped) { st.mode = "settle"; acc = 0; ballStopped(); }
    }
  }
  if (st.mode === "drop") {
    st.dropT += dt;
    const u = Math.min(1, st.dropT / 0.32);
    const c = cupGroup.position;
    ball.position.set(THREE.MathUtils.lerp(st.dropFrom.x, c.x, u), st.dropFrom.y - (CUP_DEPTH - BALL_R + 0.02) * u * u, THREE.MathUtils.lerp(st.dropFrom.z, c.z, u));
    if (u >= 1) { st.pos.copy(hole.cup); toast("홀인!", 1300); finishHole("in"); }
  }
  // camera
  cameraTarget(camT);
  const k = 1 - Math.exp(-dt * (st.mode === "aim" && !st.top ? 9 : 2.6));
  st.camPos.lerp(camT.pos, k); st.camLook.lerp(camT.look, k);
  applyCamera();
  if (SIDE_CAM) {   // debug: look at the stroke from the side
    const r = new THREE.Vector3(-st.aim.y, 0, st.aim.x);
    camera.position.copy(putter.root.position).addScaledVector(r, -1.6).add(new THREE.Vector3(0, 0.45, 0));
    camera.up.set(0, 1, 0); camera.lookAt(putter.root.position.clone().add(new THREE.Vector3(0, 0.3, 0)));
  }
  // sun shadow follows the ball
  sun.position.copy(ball.position).addScaledVector(SUN_DIR, 12); sun.target.position.copy(ball.position);
  updateMarkers();
  // the putter and the flagstick get out of the way when the camera passes close to them
  const hp = putter.root.position;
  putter.root.visible = st.mode === "aim" || st.mode === "swing" || camera.position.distanceTo(hp) > 1.1;
  const pd = Math.hypot(camera.position.x - cupGroup.position.x, camera.position.z - cupGroup.position.z);
  const fade = THREE.MathUtils.clamp((pd - 0.6) / 1.6, 0.12, 1);
  cupGroup.userData.fadeMats.forEach((m) => { m.opacity = fade; m.transparent = fade < 1; m.depthWrite = fade >= 1; });
  dotU.uTime.value = clock;
  waveFlag(clock);
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ start */
if (new URLSearchParams(location.search).has("debug")) window.__game = { st, get hole() { return hole; }, putter, ball, camera, cupGroup };
resize();
const params = new URLSearchParams(location.search);
startHole(parseInt(params.get("hole"), 10) || 1 + Math.floor(Math.random() * 50));
requestAnimationFrame((t) => { last = t; frame(t); });
loadPutter((f) => (ui.bar.style.transform = `scaleX(${f})`)).then(() => {
  placePutter();
  ui.loading.classList.add("is-done");
  setTimeout(() => (ui.loading.hidden = true), 600);
  if (window.gtag) window.gtag("event", "putting_game_start");
});
