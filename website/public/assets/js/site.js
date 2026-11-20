/* GRAZR website behaviour: header, scroll-driven hero, feature clips, 3D viewer, options, photos. */
(function () {
  "use strict";
  var doc = document.documentElement;
  doc.classList.remove("no-js");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SHAFT = {
    black: { color: [0.004, 0.004, 0.0045, 1], metallic: 0, roughness: 0.12, clearcoat: 1 },
    silver: { color: [0.08, 0.083, 0.088, 1], metallic: 0.3, roughness: 0.6, clearcoat: 0 }
  };
  var shaftState = "black";

  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function easeOut(x) { return 1 - Math.pow(1 - x, 3); }

  /* header turns solid once the page scrolls */
  var header = document.querySelector("[data-header]");
  function onScrollHeader() {
    if (header) header.classList.toggle("is-solid", window.scrollY > 24 || !document.querySelector("[data-hero]"));
  }
  window.addEventListener("scroll", onScrollHeader, { passive: true });
  onScrollHeader();

  /* ---------------------------------------------------------------- hero image sequence */
  function initHero() {
    var hero = document.querySelector("[data-hero]");
    if (!hero) return;
    var canvas = hero.querySelector("[data-hero-canvas]");
    var ctx = canvas.getContext("2d");
    var N = parseInt(hero.getAttribute("data-frames"), 10);
    var INTRO = Math.round(N * 0.42);           // frames played on load, the rest follow the scroll
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var big = Math.max(window.innerWidth, window.innerHeight) * dpr > 1300;
    var dir = "/media/hero/" + (big ? "1600" : "960") + "/";
    var imgs = new Array(N), ok = new Array(N);
    var want = reduceMotion ? N - 1 : 0, shown = -1, introDone = reduceMotion, introStart = 0;

    function src(i) { return dir + ("00" + i).slice(-3) + ".webp"; }
    function load(i, cb) {
      if (imgs[i]) { if (cb && ok[i]) cb(); return; }
      var im = new Image();
      im.decoding = "async";
      im.onload = function () { ok[i] = true; if (cb) cb(); requestDraw(); };
      im.src = src(i);
      imgs[i] = im;
    }
    // load order: the frame we need first, then coarse-to-fine so scrubbing always has something close
    var order = [], seen = {};
    function push(i) { if (!seen[i] && i >= 0 && i < N) { seen[i] = 1; order.push(i); } }
    push(reduceMotion ? N - 1 : 0);
    for (var i = 0; i <= INTRO; i++) push(i);
    [8, 4, 2, 1].forEach(function (s) { for (var k = 0; k < N; k += s) push(k); });
    var next = 0, active = 0;
    function pump() {
      while (active < 6 && next < order.length) {
        active++;
        load(order[next++], function () { active--; pump(); });
      }
    }

    function nearest(i) {
      for (var d = 0; d < N; d++) {
        if (i - d >= 0 && ok[i - d]) return i - d;
        if (i + d < N && ok[i + d]) return i + d;
      }
      return -1;
    }
    var raf = 0;
    function requestDraw() { if (!raf) raf = requestAnimationFrame(draw); }
    function size() {
      var w = canvas.clientWidth, h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      shown = -1; requestDraw();
    }
    function draw() {
      raf = 0;
      var i = nearest(Math.round(want));
      if (i < 0 || i === shown) return;
      shown = i;
      var im = imgs[i], cw = canvas.width, ch = canvas.height, iw = im.naturalWidth, ih = im.naturalHeight;
      var s, dx, dy;
      if (cw / ch >= 1.15) {                     // landscape: cover, nudged up to leave the lower band for the copy
        s = Math.max(cw / iw, ch / ih) * 1.1;
        dx = (cw - iw * s) / 2; dy = (ch - ih * s) / 2 - ch * 0.045;
      } else {                                   // portrait: fit the width a little larger, head above the copy
        s = (cw / iw) * 1.32;
        dx = (cw - iw * s) / 2; dy = ch * 0.40 - (ih * s) / 2;
      }
      ctx.fillStyle = "#000"; ctx.fillRect(0, 0, cw, ch);
      ctx.drawImage(im, dx, dy, iw * s, ih * s);
    }
    function scrollTarget() {
      var r = hero.getBoundingClientRect();
      var span = hero.offsetHeight - window.innerHeight;
      var p = clamp(-r.top / Math.max(span, 1), 0, 1);
      hero.classList.toggle("is-scrolled", p > 0.04);
      return INTRO + p * (N - 1 - INTRO);
    }
    function introTick(t) {
      if (introDone) return;
      if (!introStart) introStart = t;
      var u = clamp((t - introStart) / 2600, 0, 1);
      want = Math.max(easeOut(u) * INTRO, 0);
      if (u > 0.55) hero.classList.add("is-ready");
      requestDraw();
      if (u < 1) requestAnimationFrame(introTick); else { introDone = true; want = scrollTarget(); requestDraw(); }
    }
    window.addEventListener("scroll", function () {
      if (!introDone && window.scrollY > 10) { introDone = true; hero.classList.add("is-ready"); }
      if (introDone) { want = scrollTarget(); requestDraw(); }
    }, { passive: true });
    window.addEventListener("resize", size);
    size();
    pump();
    if (reduceMotion) { hero.classList.add("is-ready"); }
    else {
      // start the intro once the first stretch of frames is in (or after a short wait)
      var started = false;
      var start = function () { if (!started) { started = true; requestAnimationFrame(introTick); } };
      var check = setInterval(function () {
        var have = 0; for (var k = 0; k <= INTRO; k++) if (ok[k]) have++;
        if (have > INTRO * 0.8) { clearInterval(check); start(); }
      }, 80);
      setTimeout(function () { clearInterval(check); start(); }, 2500);
    }
  }

  /* ---------------------------------------------------------------- feature clips: play once in view */
  function initClips() {
    var clips = [].slice.call(document.querySelectorAll("[data-clip]"));
    if (!clips.length) return;
    clips.forEach(function (v) {
      var replay = v.parentNode.querySelector("[data-replay]");
      v.addEventListener("ended", function () { if (replay) replay.hidden = false; });
      v.addEventListener("play", function () { if (replay) replay.hidden = true; });
      if (replay) replay.addEventListener("click", function () { v.currentTime = 0; v.play(); });
      if (reduceMotion) { v.controls = true; }
    });
    if (reduceMotion || !("IntersectionObserver" in window)) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var v = e.target;
        if (e.isIntersecting && e.intersectionRatio >= 0.5) {
          if (v.ended) v.currentTime = 0;
          if (v.paused) { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
        } else if (!v.paused) {
          v.pause();
        }
      });
    }, { threshold: [0, 0.5] });
    clips.forEach(function (v) { io.observe(v); });
    // warm up the next clips shortly before they scroll in
    var warm = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.preload = "auto"; warm.unobserve(e.target); } });
    }, { rootMargin: "600px 0px" });
    clips.forEach(function (v) { warm.observe(v); });
  }

  /* the impact sound: restart the stroke clip with sound on */
  function initSound() {
    var btn = document.querySelector("[data-sound]");
    var v = document.querySelector("[data-sound-clip]");
    if (!btn || !v) return;
    var label = btn.querySelector("span");
    function reset() { v.muted = true; btn.classList.remove("is-playing"); label.textContent = btn.getAttribute("data-label"); }
    btn.addEventListener("click", function () {
      if (!v.muted && !v.paused) { reset(); return; }
      v.muted = false; v.currentTime = 0;
      var p = v.play(); if (p && p.catch) p.catch(reset);
      btn.classList.add("is-playing"); label.textContent = btn.getAttribute("data-playing");
    });
    v.addEventListener("ended", reset);
    v.addEventListener("pause", function () { if (!v.ended) reset(); });
  }

  /* ---------------------------------------------------------------- shaft option (buy section + 3D) */
  function applyShaft(mv, key) {
    if (!mv || !mv.model) return;
    var m = mv.model.getMaterialByName && mv.model.getMaterialByName("Graphite_Shaft_GlossBlack");
    if (!m) return;
    var s = SHAFT[key], pbr = m.pbrMetallicRoughness;
    pbr.setBaseColorFactor(s.color);
    pbr.setMetallicFactor(s.metallic);
    pbr.setRoughnessFactor(s.roughness);
    if (m.setClearcoatFactor) m.setClearcoatFactor(s.clearcoat);
  }
  function setShaft(key) {
    shaftState = key;
    [].forEach.call(document.querySelectorAll("[data-shaft-input]"), function (r) { r.checked = r.value === key; });
    [].forEach.call(document.querySelectorAll("[data-buy-img]"), function (im) {
      im.classList.toggle("is-on", im.getAttribute("data-buy-img") === key);
    });
    applyShaft(document.querySelector(".viewer model-viewer"), key);
  }
  function initOptions() {
    [].forEach.call(document.querySelectorAll("[data-shaft-input]"), function (r) {
      r.addEventListener("change", function () { if (r.checked) setShaft(r.value); });
    });
  }

  /* ---------------------------------------------------------------- 3D viewer, loaded on demand */
  function initViewer() {
    var box = document.querySelector("[data-viewer]");
    if (!box) return;
    var btn = box.querySelector("[data-viewer-load]");
    btn.addEventListener("click", function () {
      btn.disabled = true;
      btn.querySelector("span").textContent = btn.getAttribute("data-loading");
      import("/assets/vendor/model-viewer.min.js").then(function () {
        var mv = document.createElement("model-viewer");
        var attrs = {
          src: box.getAttribute("data-src"), alt: box.getAttribute("data-alt"),
          "camera-controls": "", "touch-action": "pan-y", "interaction-prompt": "auto",
          ar: "", "ar-modes": "webxr scene-viewer quick-look", "ar-scale": "fixed",
          "shadow-intensity": "1", "shadow-softness": "0.8", exposure: "1.15", "environment-image": "neutral",
          "camera-target": "0m 0.016m -0.034m", "camera-orbit": "-32deg 76deg 0.30m", "field-of-view": "30deg",
          "min-camera-orbit": "auto auto 0.18m", "max-camera-orbit": "auto auto 2.6m"
        };
        Object.keys(attrs).forEach(function (k) { mv.setAttribute(k, attrs[k]); });
        var ar = document.createElement("button");
        ar.setAttribute("slot", "ar-button"); ar.className = "btn btn-primary btn-small ar-btn"; ar.type = "button";
        ar.textContent = box.getAttribute("data-ar");
        mv.appendChild(ar);
        mv.addEventListener("load", function () { box.classList.add("is-live"); applyShaft(mv, shaftState); });
        mv.addEventListener("error", function () { btn.disabled = false; });
        box.appendChild(mv);
      }).catch(function () { btn.disabled = false; });
    });
  }

  /* ---------------------------------------------------------------- photo lightbox */
  function initPhotos() {
    var dlg = document.querySelector("[data-lightbox]");
    if (!dlg || !dlg.showModal) return;
    var img = dlg.querySelector("img");
    [].forEach.call(document.querySelectorAll("[data-photo]"), function (b) {
      b.addEventListener("click", function () {
        img.src = b.getAttribute("data-photo"); img.alt = b.getAttribute("aria-label") || "";
        dlg.showModal();
      });
    });
    dlg.addEventListener("click", function (e) { if (e.target === dlg || e.target === img) dlg.close(); });
  }

  /* ---------------------------------------------------------------- reveal on scroll */
  function initReveal() {
    var els = [].slice.call(document.querySelectorAll("[data-reveal]"));
    if (reduceMotion || !("IntersectionObserver" in window)) { els.forEach(function (e) { e.classList.add("in"); }); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    els.forEach(function (e) { io.observe(e); });
  }

  initHero(); initClips(); initSound(); initOptions(); initViewer(); initPhotos(); initReveal();
})();

/* KakaoTalk chat button: keep it off the opening film, show it once the visitor scrolls past it */
(function () {
  var fab = document.querySelector(".kakao-fab");
  if (!fab || !document.querySelector(".hero-sticky")) return;
  var tick = function () { fab.classList.toggle("is-hidden", window.scrollY < window.innerHeight * 0.9); };
  tick();
  window.addEventListener("scroll", tick, { passive: true });
  window.addEventListener("resize", tick);
})();
