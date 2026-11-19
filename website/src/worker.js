// GRAZR site Worker: static files are served from ./public; only /api/* runs here.
// POST /api/confirm approves a Toss Payments widget payment after checking the amount.
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
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

    const secret = env.TOSS_SECRET_KEY || env.TOSS_TEST_SECRET_KEY;
    if (!secret) return json({ code: "NOT_CONFIGURED", message: "결제 설정이 아직 완료되지 않았습니다." }, 500);

    const r = await fetch("https://api.tosspayments.com/v1/payments/confirm", {
      method: "POST",
      headers: { Authorization: "Basic " + btoa(secret + ":"), "Content-Type": "application/json" },
      body: JSON.stringify({ paymentKey, orderId, amount }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return json({ code: d.code || "CONFIRM_FAILED", message: d.message || "결제 승인에 실패했습니다." }, r.status);
    return json({
      orderId: d.orderId, orderName: d.orderName, totalAmount: d.totalAmount, method: d.method,
      approvedAt: d.approvedAt, receiptUrl: d.receipt && d.receipt.url, status: d.status,
      isTest: secret.startsWith("test_"),
    });
  },
};
