/* GRAZR order admin: list site orders, enter tracking numbers, tell the buyer, refund through Toss. */
(function () {
  "use strict";
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var KAKAO = "https://pf.kakao.com/_DFdvX/chat";
  var state = { tab: "paid", couriers: {} };
  var app = $("[data-app]"), login = $("[data-login]"), notice = $("[data-notice]"), logoutBtn = $("[data-logout]");

  function api(path, body) {
    var opt = { credentials: "same-origin", headers: {} };
    if (body !== undefined) {
      opt.method = "POST";
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    return fetch("/api/admin" + path, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { d._status = r.status; return d; });
    });
  }

  function won(n) { return Number(n || 0).toLocaleString("ko-KR") + "원"; }
  function when(t) {
    var d = new Date(t), p = function (n) { return (n < 10 ? "0" : "") + n; };
    return d.getFullYear() + "." + p(d.getMonth() + 1) + "." + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }
  function phone(p) {
    var s = String(p || "").replace(/[^0-9]/g, "");
    return s.length === 11 ? s.slice(0, 3) + "-" + s.slice(3, 7) + "-" + s.slice(7) : s.length === 10 ? s.slice(0, 3) + "-" + s.slice(3, 6) + "-" + s.slice(6) : (p || "");
  }
  var STATUS = { paid: "발송 대기", shipped: "발송 완료", canceled: "취소" };
  function courierName(k) { return state.couriers[k] || "로젠택배"; }
  function trackUrl(o) {
    return "https://search.naver.com/search.naver?query=" + encodeURIComponent(courierName(o.courier) + " " + o.tracking);
  }
  function message(o) {
    return "[GRAZR] " + (o.name || "고객") + "님, 주문하신 " + (o.orderName || "GRAZR DP-301 퍼터") +
      (o.option ? " (" + o.option + ")" : "") + "를 발송했습니다.\n" +
      courierName(o.courier) + " 송장번호: " + o.tracking + "\n" +
      "배송 조회: " + trackUrl(o) + "\n" +
      "문의: 카카오톡 채널 'GRAZR 그레이저' " + KAKAO + "\n감사합니다.";
  }
  function copy(text, btn) {
    var done = function () {
      var t = btn.textContent; btn.classList.add("done"); btn.textContent = "복사됨";
      setTimeout(function () { btn.classList.remove("done"); btn.textContent = t; }, 1400);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { prompt("복사하세요", text); });
    else { prompt("복사하세요", text); }
  }

  function show(view) {
    login.hidden = view !== "login";
    app.hidden = view !== "app";
    logoutBtn.hidden = view !== "app";
  }
  function note(msg) { notice.textContent = msg || ""; notice.hidden = !msg; }

  function load() {
    return api("/orders?status=" + state.tab).then(function (d) {
      if (d._status === 401) { show("login"); $("#pw").focus(); return; }
      if (d._status !== 200) { show("none"); note(d.message || "주문을 불러오지 못했습니다."); return; }
      note(d.live === false ? "지금은 테스트 결제 키로 운영 중입니다. 실제 돈이 오가지 않습니다." : "");
      state.couriers = d.couriers || {};
      show("app");
      Object.keys(d.counts || {}).forEach(function (k) { var b = $('[data-count="' + k + '"]'); if (b) b.textContent = d.counts[k]; });
      [].forEach.call(document.querySelectorAll("[data-tab]"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-tab") === state.tab)); });
      var list = $("[data-list]");
      list.textContent = "";
      (d.orders || []).forEach(function (o) { list.appendChild(card(o)); });
      $("[data-empty]").hidden = (d.orders || []).length > 0;
    }).catch(function () { note("서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요."); });
  }

  function card(o) {
    var el = document.importNode($("template[data-card]").content, true).firstElementChild;
    fillCard(el, o);
    var err = function (m) { $("[data-err]", el).textContent = m || ""; };
    var busy = function (btn, on) { if (btn) btn.disabled = on; };
    var update = function (d) {
      if (d.order) {
        var open = el.open, fresh = card(d.order);
        fresh.open = open; el.replaceWith(fresh);
        if (d.order.status !== state.tab && state.tab !== "all") setTimeout(load, 900);
        else refreshCounts();
        return fresh;
      }
      err(d.message || "처리하지 못했습니다.");
    };

    var sel = $("[data-couriers]", el);
    Object.keys(state.couriers).forEach(function (k) {
      var op = document.createElement("option"); op.value = k; op.textContent = state.couriers[k]; sel.appendChild(op);
    });
    sel.value = o.courier || "logen";

    $("[data-ship]", el).addEventListener("submit", function (e) {
      e.preventDefault();
      var f = e.target, btn = $("button", f);
      busy(btn, true); err("");
      api("/orders/" + o.orderId + "/ship", { courier: f.courier.value, tracking: f.tracking.value })
        .then(function (d) { busy(btn, false); var n = update(d); if (n) n.open = true; });
    });
    $("[data-unship]", el).addEventListener("click", function () {
      if (!confirm("발송 처리를 되돌릴까요? 송장번호는 남아 있습니다.")) return;
      api("/orders/" + o.orderId + "/unship", {}).then(update);
    });
    $("[data-note]", el).addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = $("button", e.target);
      busy(btn, true);
      api("/orders/" + o.orderId + "/note", { note: e.target.note.value }).then(function (d) {
        busy(btn, false);
        if (d.order) { btn.textContent = "저장됨"; setTimeout(function () { btn.textContent = "메모 저장"; }, 1400); } else err(d.message);
      });
    });
    $("[data-sync]", el).addEventListener("click", function (e) {
      var btn = e.target; busy(btn, true); err("");
      api("/orders/" + o.orderId + "/sync", {}).then(function (d) {
        busy(btn, false);
        if (!d.order) { err(d.message); return; }
        var n = update(d);
        if (n) { n.open = true; $("[data-err]", n).textContent = "토스페이먼츠 상태: " + (d.toss && d.toss.status) + " · 남은 금액 " + won(d.toss && d.toss.balanceAmount); }
      });
    });
    $("[data-cancel]", el).addEventListener("click", function (e) {
      var reason = prompt("결제를 전액 취소(환불)합니다. 되돌릴 수 없습니다.\n취소 사유를 입력하세요.", "고객 요청");
      if (reason === null) return;
      var btn = e.target; busy(btn, true); err("");
      api("/orders/" + o.orderId + "/cancel", { reason: reason }).then(function (d) { busy(btn, false); update(d); });
    });
    [].forEach.call(el.querySelectorAll("[data-copy]"), function (b) {
      b.addEventListener("click", function (e) {
        e.preventDefault();
        var k = b.getAttribute("data-copy");
        copy(k === "message" ? message(o) : k === "phone" ? phone(o.phone) : (o[k] || ""), b);
      });
    });
    return el;
  }

  function fillCard(el, o) {
    var f = function (k) { return el.querySelector('[data-f="' + k + '"]'); };
    f("when").textContent = when(o.created || o.approvedAt);
    var st = f("status"); st.textContent = STATUS[o.status] || o.status; st.className = "pill " + o.status;
    f("name").textContent = o.name || "(이름 없음)";
    if (o.test) { var t = document.createElement("span"); t.className = "tag-test"; t.textContent = "테스트"; f("name").appendChild(t); }
    f("what").textContent = (o.option || "") + " × " + (o.qty || 1);
    f("amount").textContent = won(o.amount);
    f("name2").textContent = o.name || "";
    var ph = f("phone"); ph.textContent = phone(o.phone); ph.href = "tel:" + String(o.phone || "").replace(/[^0-9]/g, "");
    f("address").textContent = o.address || "";
    f("memo").textContent = o.memo || "-";
    f("email").textContent = o.email || "-";
    f("option").textContent = (o.option || "-") + " / " + (o.qty || 1) + "개";
    f("pay").textContent = won(o.amount) + " · " + (o.method || "") + " · " + when(o.approvedAt);
    var rc = f("receipt"); if (o.receiptUrl) rc.href = o.receiptUrl; else rc.remove();
    f("orderId").textContent = o.orderId;
    el.querySelector("[data-note] textarea").value = o.note || "";

    var shipForm = el.querySelector("[data-ship]"), shipped = el.querySelector("[data-shipped]");
    shipForm.hidden = o.status !== "paid";
    shipped.hidden = !(o.status === "shipped" || (o.status === "canceled" && o.tracking));
    if (o.tracking) {
      shipForm.tracking.value = o.tracking;
      f("courier").textContent = courierName(o.courier);
      f("tracking").textContent = o.tracking;
      f("shippedAt").textContent = o.shippedAt ? when(o.shippedAt) : "";
      var msg = message(o), num = String(o.phone || "").replace(/[^0-9]/g, "");
      f("sms").href = "sms:" + num + "?&body=" + encodeURIComponent(msg);
      var m = f("mail");
      if (o.email) m.href = "mailto:" + o.email + "?subject=" + encodeURIComponent("[GRAZR] 주문하신 상품을 발송했습니다") + "&body=" + encodeURIComponent(msg);
      else m.remove();
      f("track").href = trackUrl(o);
    }
    el.querySelector("[data-unship]").hidden = o.status !== "shipped";
    el.querySelector("[data-cancel]").hidden = o.status === "canceled";
  }

  function refreshCounts() {
    api("/orders?status=" + state.tab).then(function (d) {
      Object.keys(d.counts || {}).forEach(function (k) { var b = $('[data-count="' + k + '"]'); if (b) b.textContent = d.counts[k]; });
    });
  }

  login.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = $("button", login); btn.disabled = true; $("[data-login-err]").textContent = "";
    api("/login", { password: login.password.value }).then(function (d) {
      btn.disabled = false;
      if (d.ok) { login.password.value = ""; load(); } else $("[data-login-err]").textContent = d.message || "로그인하지 못했습니다.";
    });
  });
  logoutBtn.addEventListener("click", function () { api("/logout", {}).then(function () { show("login"); }); });
  [].forEach.call(document.querySelectorAll("[data-tab]"), function (b) {
    b.addEventListener("click", function () { state.tab = b.getAttribute("data-tab"); load(); });
  });
  load();
})();
