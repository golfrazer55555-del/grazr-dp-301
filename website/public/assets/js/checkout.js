/* GRAZR checkout: Toss Payments widget (v2) + result page. The amount is re-checked on the server. */
(function () {
  "use strict";
  function won(n) { return Number(n).toLocaleString("ko-KR") + "원"; }
  function store(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function track(name, params) { try { if (window.gtag) window.gtag("event", name, params); } catch (e) {} }
  function load(k) { try { return JSON.parse(sessionStorage.getItem(k) || "null"); } catch (e) { return null; } }

  var box = document.querySelector("[data-checkout]");
  if (box) initCheckout(box);
  var res = document.querySelector("[data-result]");
  if (res) initResult(res);

  function initCheckout(box) {
    var price = parseInt(box.getAttribute("data-price"), 10);
    var product = box.getAttribute("data-product") || "dp-301";
    var productName = box.getAttribute("data-name") || "GRAZR DP-301";
    var form = box.querySelector("[data-co-form]");
    var errEl = box.querySelector("[data-co-error]");
    var payBtn = box.querySelector("[data-pay]");
    var agree = box.querySelector("[data-agree]");
    var widgets = null;
    function qty() { return parseInt(form.qty.value, 10) || 1; }
    function amount() { return price * qty(); }
    function err(m) { errEl.textContent = m || ""; }
    function refresh() {
      [].forEach.call(box.querySelectorAll("[data-total]"), function (e) { e.textContent = won(amount()); });
    }
    [].forEach.call(form.querySelectorAll("[data-shaft-input]"), function (r) {
      r.addEventListener("change", function () {
        [].forEach.call(box.querySelectorAll("[data-buy-img]"), function (im) {
          im.classList.toggle("is-on", im.getAttribute("data-buy-img") === r.value);
        });
      });
    });
    var want = new URLSearchParams(location.search).get("shaft");
    [].forEach.call(form.querySelectorAll("[data-shaft-input]"), function (r) {
      if (want && r.value === want && !r.checked) { r.checked = true; r.dispatchEvent(new Event("change")); }
    });
    form.qty.addEventListener("change", function () {
      refresh();
      if (widgets) widgets.setAmount({ currency: "KRW", value: amount() });
    });
    refresh();

    box.querySelector("[data-postcode]").addEventListener("click", function () {
      if (!window.daum || !daum.Postcode) { err("주소 검색을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."); return; }
      new daum.Postcode({
        oncomplete: function (d) {
          form.zip.value = d.zonecode;
          form.addr1.value = d.roadAddress || d.jibunAddress;
          form.addr2.focus();
        }
      }).open();
    });

    if (!window.TossPayments) { err("결제창을 불러오지 못했습니다. 새로고침해 주세요."); return; }
    try {
      var tp = TossPayments(box.getAttribute("data-client-key"));
      widgets = tp.widgets({ customerKey: TossPayments.ANONYMOUS });
      widgets.setAmount({ currency: "KRW", value: amount() }).then(function () {
        return Promise.all([
          widgets.renderPaymentMethods({ selector: "#payment-method", variantKey: "DEFAULT" }),
          widgets.renderAgreement({ selector: "#agreement", variantKey: "AGREEMENT" })
        ]);
      }).then(function () { payBtn.disabled = false; })
        .catch(function (e) { err("결제창을 불러오지 못했습니다. (" + (e && e.message || e) + ")"); });
    } catch (e) { err("결제창을 불러오지 못했습니다. (" + (e && e.message || e) + ")"); return; }

    function value(n) { return (form[n].value || "").trim(); }
    function validate() {
      var phone = value("phone").replace(/[^0-9]/g, "");
      if (!value("name")) return "이름을 입력해 주세요.";
      if (!/^01[0-9]{8,9}$/.test(phone)) return "휴대폰 번호를 확인해 주세요.";
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value("email"))) return "이메일 주소를 확인해 주세요.";
      if (!value("zip") || !value("addr1")) return "주소 검색으로 배송지를 입력해 주세요.";
      if (!agree.checked) return "주문 내용과 개인정보 수집·이용에 동의해 주세요.";
      return "";
    }

    payBtn.addEventListener("click", function () {
      var problem = validate();
      if (problem) { err(problem); return; }
      err("");
      var opt = form.querySelector("[data-shaft-input]:checked");
      var label = opt.getAttribute("data-label");
      var q = qty();
      var orderId = "GRAZR-" + Date.now().toString(36).toUpperCase() + "-" + Math.random().toString(36).slice(2, 8).toUpperCase();
      var orderName = productName + " " + label + (q > 1 ? " x" + q : "");
      var address = "(" + value("zip") + ") " + value("addr1") + " " + value("addr2");
      store("grazr-order-" + orderId, { product: product, orderName: orderName, name: value("name"), address: address,
        phone: value("phone").replace(/[^0-9]/g, ""), email: value("email"), memo: value("memo"), option: label, qty: String(q) });
      payBtn.disabled = true;
      track("begin_checkout", { currency: "KRW", value: price * q,
        items: [{ item_id: product, item_name: productName, item_variant: label, price: price, quantity: q }] });
      widgets.requestPayment({
        orderId: orderId,
        orderName: orderName,
        successUrl: location.origin + "/checkout/success/",
        failUrl: location.origin + "/checkout/fail/",
        customerName: value("name"),
        customerEmail: value("email"),
        customerMobilePhone: value("phone").replace(/[^0-9]/g, ""),
        metadata: { product: product, option: label, qty: String(q), address: address.slice(0, 300), memo: value("memo").slice(0, 100) }
      }).catch(function (e) {
        payBtn.disabled = false;
        if (e && e.code === "USER_CANCEL") return;
        err((e && e.message) || "결제를 시작하지 못했습니다.");
      });
    });
  }

  function initResult(el) {
    var q = new URLSearchParams(location.search);
    var title = el.querySelector("[data-r-title]"), msg = el.querySelector("[data-r-msg]");
    var detail = el.querySelector("[data-r-detail]"), retry = el.querySelector("[data-r-retry]");
    function row(k, v) {
      var d = document.createElement("div"), dt = document.createElement("dt"), dd = document.createElement("dd");
      dt.textContent = k; dd.textContent = v; d.appendChild(dt); d.appendChild(dd); detail.appendChild(d);
    }
    var placed = load("grazr-order-" + (q.get("orderId") || "")) || {};
    if (placed.product && placed.product !== "dp-301") retry.href = "/checkout/" + placed.product + "/";
    if (el.getAttribute("data-result") === "fail") {
      msg.textContent = (q.get("message") || "결제가 취소되었거나 실패했습니다.") + (q.get("code") ? " (" + q.get("code") + ")" : "");
      return;
    }
    var paymentKey = q.get("paymentKey"), orderId = q.get("orderId"), amount = q.get("amount");
    if (!paymentKey || !orderId || !amount) {
      title.textContent = "주문 정보를 찾을 수 없습니다"; msg.textContent = ""; retry.hidden = false; return;
    }
    function show(r) {
      title.textContent = "주문이 완료됐습니다";
      msg.textContent = "결제 후 1일 이내에 로젠택배로 발송합니다. 결제 영수증은 아래에서 확인하실 수 있습니다.";
      var o = load("grazr-order-" + orderId) || {};
      detail.hidden = false;
      row("주문번호", r.orderId);
      row("상품", r.orderName || o.orderName || "");
      row("결제 금액", won(r.totalAmount));
      if (r.method) row("결제 수단", r.method);
      if (o.name) row("받는 분", o.name);
      if (o.address) row("배송지", o.address);
      if (r.receiptUrl) {
        var d = document.createElement("div"), dt = document.createElement("dt"), dd = document.createElement("dd"), a = document.createElement("a");
        dt.textContent = "영수증"; a.href = r.receiptUrl; a.target = "_blank"; a.rel = "noopener"; a.textContent = "영수증 보기";
        dd.appendChild(a); d.appendChild(dt); d.appendChild(dd); detail.appendChild(d);
      }
      if (r.isTest) el.querySelector("[data-r-test]").hidden = false;
    }
    var done = load("grazr-done-" + orderId);
    if (done) { show(done); return; }
    fetch("/api/confirm", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paymentKey: paymentKey, orderId: orderId, amount: Number(amount),
        product: (load("grazr-order-" + orderId) || {}).product, shipping: load("grazr-order-" + orderId) || {} })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (x) {
        if (!x.ok) throw x.j;
        store("grazr-done-" + orderId, x.j);
        show(x.j);
        if (!x.j.isTest) {
          var o = load("grazr-order-" + orderId) || {}, n = Number(o.qty) || 1;
          track("purchase", { transaction_id: x.j.orderId, currency: "KRW", value: x.j.totalAmount,
            items: [{ item_id: o.product || "dp-301", item_name: x.j.orderName || o.orderName || "", item_variant: o.option || "",
                      price: Math.round(x.j.totalAmount / n), quantity: n }] });
        }
      }).catch(function (e) {
        title.textContent = "결제가 완료되지 않았습니다";
        msg.textContent = ((e && e.message) || "결제 승인 중 문제가 생겼습니다.") + " 결제되지 않았으니 다시 시도해 주세요.";
        retry.hidden = false;
      });
  }
})();
