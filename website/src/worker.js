// GRAZR site Worker: static files are served from ./public; only /api/* runs here.
// POST /api/confirm approves a Toss Payments widget payment after checking the amount, then
// (when the ORDER_MAIL send_email binding exists) emails the order and shipping details to GRAZR.
// GET /api/mail-test?key=... sends a sample order mail; it only exists while the secret MAIL_TEST_KEY is set.
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });

const clip = (v, n) => (typeof v === "string" ? v.replace(/[\r\n\t]+/g, " ").trim().slice(0, n) : "");
const b64 = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));
// RFC 2047: keep each encoded word short (split by characters, folded onto continuation lines)
const word = (s) => (Array.from(s).join("").match(/[\s\S]{1,12}/gu) || [""]).map((c) => "=?UTF-8?B?" + b64(c) + "?=").join("\r\n ");
const won = (n) => Number(n).toLocaleString("ko-KR") + "원";
const kst = (iso) => {
  const d = iso ? new Date(iso) : new Date();
  return new Date(d.getTime() + 9 * 3600e3).toISOString().replace("T", " ").slice(0, 16) + " (KST)";
};

function sendMail(env, m) {
  return import("cloudflare:email").then(({ EmailMessage }) => env.ORDER_MAIL.send(new EmailMessage(m.from, m.to, m.raw)));
}

async function mailTest(request, env, url) {
  const key = env.MAIL_TEST_KEY;
  if (!key || request.method !== "GET" || url.searchParams.get("key") !== key) return env.ASSETS.fetch(request);
  if (!env.ORDER_MAIL) return json({ sent: false, message: "ORDER_MAIL 설정이 없습니다." }, 500);
  const d = {
    orderId: "TEST-" + Date.now(), orderName: "GRAZR DP-301 퍼터", totalAmount: Number(env.PRICE_KRW || 385000),
    method: "카드", approvedAt: new Date().toISOString(), receipt: null,
  };
  const ship = { name: "홍길동", phone: "010-0000-0000", email: "test@example.com", address: "(00000) 테스트 주소",
    memo: "메일 테스트", option: "34인치 · 블랙 샤프트", qty: "1" };
  try {
    await sendMail(env, orderMail(env, d, ship, true));
    return json({ sent: true, message: "테스트 메일을 보냈습니다. Gmail을 확인하세요." });
  } catch (e) {
    return json({ sent: false, message: String((e && e.message) || e) }, 500);
  }
}

function orderMail(env, d, ship, isTest) {
  const from = env.ORDER_MAIL_FROM || "orders@grazr.co.kr";
  const to = env.ORDER_MAIL_TO || "grazrofficial@gmail.com";
  const lines = [
    isTest ? "※ 테스트 결제입니다. 실제 결제·배송이 아닙니다.\n" : "",
    "새 주문이 들어왔습니다.",
    "",
    "[주문]",
    "주문번호: " + d.orderId,
    "상품: " + d.orderName,
    "옵션: " + (ship.option || "-") + " / 수량 " + (ship.qty || "-") + "개",
    "결제 금액: " + won(d.totalAmount),
    "결제 수단: " + (d.method || "-"),
    "결제 시각: " + kst(d.approvedAt),
    "",
    "[받는 분]",
    "이름: " + (ship.name || "-"),
    "휴대폰: " + (ship.phone || "-"),
    "이메일: " + (ship.email || "-"),
    "주소: " + (ship.address || "-"),
    "배송 메모: " + (ship.memo || "-"),
    "",
    "영수증: " + ((d.receipt && d.receipt.url) || "-"),
    "결제 관리(취소·환불): https://app.tosspayments.com",
    "",
    "결제 후 1일 이내 발송 · 로젠택배",
  ].filter((l, i) => i > 0 || l);
  const subject = (isTest ? "[테스트] " : "") + "[GRAZR 주문] " + (ship.name || "") + " · " + d.orderName + " · " + won(d.totalAmount);
  const raw = [
    "From: " + word("GRAZR 주문 알림") + " <" + from + ">",
    "To: <" + to + ">",
    "Subject: " + word(subject),
    "Date: " + new Date().toUTCString(),
    "Message-ID: <" + d.orderId + "." + Date.now() + "@grazr.co.kr>",
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    b64(lines.join("\n")).replace(/.{76}/g, "$&\r\n"),
  ].join("\r\n");
  return { from, to, raw };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/api/mail-test") return mailTest(request, env, url);
    if (url.pathname !== "/api/confirm") return env.ASSETS.fetch(request);
    if (request.method !== "POST") return json({ code: "METHOD_NOT_ALLOWED", message: "허용되지 않은 요청입니다." }, 405);

    let body;
    try { body = await request.json(); } catch { return json({ code: "BAD_REQUEST", message: "잘못된 요청입니다." }, 400); }
    const { paymentKey, orderId } = body || {};
    const amount = Number(body && body.amount);
    const price = Number(env.PRICE_KRW || 385000);
    const maxQty = Number(env.MAX_QTY || 3);
    if (typeof paymentKey !== "string" || paymentKey.length > 200 || typeof orderId !== "string" || !/^[A-Za-z0-9_-]{6,64}$/.test(orderId))
      return json({ code: "BAD_REQUEST", message: "잘못된 주문 정보입니다." }, 400);
    // the price lives here, not in the browser: the amount must be the product price x 1..maxQty
    if (!Number.isInteger(amount) || amount < price || amount % price !== 0 || amount / price > maxQty)
      return json({ code: "INVALID_AMOUNT", message: "주문 금액이 올바르지 않습니다." }, 400);

    const secret = env.TOSS_SECRET_KEY;
    if (!secret) return json({ code: "NOT_CONFIGURED", message: "결제 설정이 아직 완료되지 않았습니다." }, 500);

    const r = await fetch("https://api.tosspayments.com/v1/payments/confirm", {
      method: "POST",
      headers: { Authorization: "Basic " + btoa(secret + ":"), "Content-Type": "application/json" },
      body: JSON.stringify({ paymentKey, orderId, amount }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return json({ code: d.code || "CONFIRM_FAILED", message: d.message || "결제 승인에 실패했습니다." }, r.status);

    const isTest = secret.startsWith("test_");
    if (env.ORDER_MAIL) {
      // shipping details come from the buyer's form; the order, amount and method come from Toss
      const s = (body && body.shipping) || {};
      const meta = d.metadata || {};
      const ship = {
        name: clip(s.name, 40), phone: clip(s.phone, 20), email: clip(s.email, 100),
        address: clip(s.address || meta.address, 300), memo: clip(s.memo || meta.memo, 100),
        option: clip(meta.option || s.option, 40), qty: String(Math.round(d.totalAmount / price)),
      };
      const m = orderMail(env, d, ship, isTest);
      const send = sendMail(env, m)
        .catch((e) => console.error("order mail failed", d.orderId, e && e.message));
      if (ctx && ctx.waitUntil) ctx.waitUntil(send); else await send;
    }
    return json({
      orderId: d.orderId, orderName: d.orderName, totalAmount: d.totalAmount, method: d.method,
      approvedAt: d.approvedAt, receiptUrl: d.receipt && d.receipt.url, status: d.status, isTest,
    });
  },
};

export { orderMail };
