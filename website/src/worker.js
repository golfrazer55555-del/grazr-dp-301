// GRAZR site Worker: static files are served from ./public; only /api/* runs here.
//   POST /api/confirm      approves a Toss Payments widget payment after checking the amount, saves the order
//                          (OrderStore) and emails it to GRAZR (ORDER_MAIL).
//   /api/admin/*           order admin used by /admin/ (password = secret ADMIN_PASSWORD).
//   GET /api/mail-test     sends a sample order mail; only exists while the secret MAIL_TEST_KEY is set.
import { DurableObject } from "cloudflare:workers";
import { EmailMessage } from "cloudflare:email";

const TOSS = "https://api.tosspayments.com/v1/payments";
const COURIERS = { logen: "로젠택배", cj: "CJ대한통운", hanjin: "한진택배", lotte: "롯데택배", post: "우체국택배", etc: "기타" };
const KEEP_MS = 5 * 365 * 24 * 3600e3;   // 전자상거래법: 대금 결제·공급 기록 5년
const SESSION_S = 30 * 24 * 3600;
// products sold on the site; the server, not the browser, decides each price
const DEFAULT_PRODUCTS = {
  "dp-301": { name: "GRAZR DP-301 퍼터", price: 385000 },
  "dp-501": { name: "GRAZR DP-501 파크골프채", price: 460000 },
};
function products(env) {
  try { return env.PRODUCTS ? JSON.parse(env.PRODUCTS) : DEFAULT_PRODUCTS; } catch { return DEFAULT_PRODUCTS; }
}

const json = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers },
  });

const clip = (v, n) => (typeof v === "string" ? v.replace(/[\r\n\t]+/g, " ").trim().slice(0, n) : "");
const b64 = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));
// RFC 2047: keep each encoded word short (split by characters, folded onto continuation lines)
const word = (s) => (Array.from(s).join("").match(/[\s\S]{1,12}/gu) || [""]).map((c) => "=?UTF-8?B?" + b64(c) + "?=").join("\r\n ");
const won = (n) => Number(n).toLocaleString("ko-KR") + "원";
const kst = (iso) => {
  const d = iso ? new Date(iso) : new Date();
  return new Date(d.getTime() + 9 * 3600e3).toISOString().replace("T", " ").slice(0, 16) + " (KST)";
};
const tossAuth = (env) => "Basic " + btoa(env.TOSS_SECRET_KEY + ":");
const store = (env) => env.ORDERS.get(env.ORDERS.idFromName("grazr"));

/* ---------------- order store (one SQLite Durable Object) ---------------- */

export class OrderStore extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.sql.exec(`CREATE TABLE IF NOT EXISTS orders (
      id TEXT PRIMARY KEY, created INTEGER NOT NULL, status TEXT NOT NULL, test INTEGER NOT NULL DEFAULT 0,
      data TEXT NOT NULL, courier TEXT, tracking TEXT, shipped_at INTEGER, note TEXT, updated INTEGER)`);
    this.sql.exec("CREATE TABLE IF NOT EXISTS login_fail (t INTEGER NOT NULL)");
  }

  add(o) {
    const now = Date.now();
    this.sql.exec("INSERT OR IGNORE INTO orders (id, created, status, test, data, updated) VALUES (?, ?, 'paid', ?, ?, ?)",
      o.orderId, now, o.test ? 1 : 0, JSON.stringify(o), now);
  }

  row(r) {
    return { ...JSON.parse(r.data), status: r.status, test: !!r.test, created: r.created, courier: r.courier,
      tracking: r.tracking, shippedAt: r.shipped_at, note: r.note || "" };
  }

  list(status) {
    this.sql.exec("DELETE FROM orders WHERE created < ?", Date.now() - KEEP_MS);
    const rows = status && status !== "all"
      ? this.sql.exec("SELECT * FROM orders WHERE status = ? ORDER BY created DESC LIMIT 300", status).toArray()
      : this.sql.exec("SELECT * FROM orders ORDER BY created DESC LIMIT 300").toArray();
    const counts = { all: 0, paid: 0, shipped: 0, canceled: 0 };
    for (const c of this.sql.exec("SELECT status, COUNT(*) AS n FROM orders GROUP BY status").toArray()) {
      counts[c.status] = c.n;
      counts.all += c.n;
    }
    return { orders: rows.map((r) => this.row(r)), counts };
  }

  get(id) {
    const r = this.sql.exec("SELECT * FROM orders WHERE id = ?", id).toArray()[0];
    return r ? this.row(r) : null;
  }

  ship(id, courier, tracking) {
    this.sql.exec("UPDATE orders SET status = 'shipped', courier = ?, tracking = ?, shipped_at = ?, updated = ? WHERE id = ? AND status != 'canceled'",
      courier, tracking, Date.now(), Date.now(), id);
    return this.get(id);
  }

  unship(id) {
    this.sql.exec("UPDATE orders SET status = 'paid', shipped_at = NULL, updated = ? WHERE id = ? AND status = 'shipped'", Date.now(), id);
    return this.get(id);
  }

  setStatus(id, status) {
    this.sql.exec("UPDATE orders SET status = ?, updated = ? WHERE id = ?", status, Date.now(), id);
    return this.get(id);
  }

  setNote(id, note) {
    this.sql.exec("UPDATE orders SET note = ?, updated = ? WHERE id = ?", note, Date.now(), id);
    return this.get(id);
  }

  // at most 10 wrong passwords per 15 minutes
  loginAllowed() {
    this.sql.exec("DELETE FROM login_fail WHERE t < ?", Date.now() - 15 * 60e3);
    return this.sql.exec("SELECT COUNT(*) AS n FROM login_fail").one().n < 10;
  }

  loginFailed() {
    this.sql.exec("INSERT INTO login_fail (t) VALUES (?)", Date.now());
  }
}

/* ---------------- order mail ---------------- */

function orderMail(env, d, ship, isTest) {
  const from = env.ORDER_MAIL_FROM || "orders@grazr.co.kr";
  const to = env.ORDER_MAIL_TO || "grazrofficial@gmail.com";
  const lines = [
    isTest ? "※ 테스트 결제입니다. 실제 결제·배송이 아닙니다.\n" : "",
    "새 주문이 들어왔습니다.",
    "",
    "[주문]",
    "주문번호: " + d.orderId,
    "상품: " + (ship.productName || d.orderName),
    "옵션: " + (ship.option || "-") + " / 수량 " + (ship.qty || "-") + "개",
    "결제 금액: " + won(d.totalAmount),
    "결제 수단: " + (d.method || "-") + (d.useEscrow ? " (에스크로: 토스 상점관리자에 배송 등록 필요)" : ""),
    "결제 시각: " + kst(d.approvedAt),
    "",
    "[받는 분]",
    "이름: " + (ship.name || "-"),
    "휴대폰: " + (ship.phone || "-"),
    "이메일: " + (ship.email || "-"),
    "주소: " + (ship.address || "-"),
    "배송 메모: " + (ship.memo || "-"),
    "",
    "주문 관리(송장 입력): https://grazr.co.kr/admin/",
    "영수증: " + ((d.receipt && d.receipt.url) || "-"),
    "결제 관리(토스페이먼츠): https://app.tosspayments.com",
    "",
    "결제 후 1일 이내 발송 · 로젠택배",
  ].filter((l, i) => i > 0 || l);
  const subject = (isTest ? "[테스트] " : "") + "[GRAZR 주문] " + (ship.name || "") + " · " + (ship.productName || d.orderName) +
    " · " + won(d.totalAmount);
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

const sendMail = (env, m) => env.ORDER_MAIL.send(new EmailMessage(m.from, m.to, m.raw));

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

/* ---------------- payment approval ---------------- */

async function confirm(request, env, ctx) {
  if (request.method !== "POST") return json({ code: "METHOD_NOT_ALLOWED", message: "허용되지 않은 요청입니다." }, 405);
  let body;
  try { body = await request.json(); } catch { return json({ code: "BAD_REQUEST", message: "잘못된 요청입니다." }, 400); }
  const { paymentKey, orderId } = body || {};
  const amount = Number(body && body.amount);
  const catalog = products(env);
  const wanted = body?.product || body?.shipping?.product;
  const productKey = typeof wanted === "string" && catalog[wanted] ? wanted : "dp-301";
  const product = catalog[productKey];
  const price = Number(product.price);
  const maxQty = Number(env.MAX_QTY || 3);
  if (typeof paymentKey !== "string" || paymentKey.length > 200 || typeof orderId !== "string" || !/^[A-Za-z0-9_-]{6,64}$/.test(orderId))
    return json({ code: "BAD_REQUEST", message: "잘못된 주문 정보입니다." }, 400);
  // the price lives here, not in the browser: the amount must be the product price x 1..maxQty
  if (!Number.isInteger(amount) || amount < price || amount % price !== 0 || amount / price > maxQty)
    return json({ code: "INVALID_AMOUNT", message: "주문 금액이 올바르지 않습니다." }, 400);
  if (!env.TOSS_SECRET_KEY) return json({ code: "NOT_CONFIGURED", message: "결제 설정이 아직 완료되지 않았습니다." }, 500);

  const r = await fetch(TOSS + "/confirm", {
    method: "POST",
    headers: { Authorization: tossAuth(env), "Content-Type": "application/json" },
    body: JSON.stringify({ paymentKey, orderId, amount }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) return json({ code: d.code || "CONFIRM_FAILED", message: d.message || "결제 승인에 실패했습니다." }, r.status);

  const isTest = env.TOSS_SECRET_KEY.startsWith("test_");
  // shipping details come from the buyer's form; the order, amount and method come from Toss
  const s = (body && body.shipping) || {};
  const meta = d.metadata || {};
  const ship = {
    name: clip(s.name, 40), phone: clip(s.phone, 20), email: clip(s.email, 100),
    address: clip(s.address || meta.address, 300), memo: clip(s.memo || meta.memo, 100),
    option: clip(meta.option || s.option, 40), qty: String(Math.round(d.totalAmount / price)),
    product: productKey, productName: product.name,
  };
  const after = [];
  if (env.ORDERS) {
    after.push(store(env).add({
      orderId: d.orderId, paymentKey: d.paymentKey || paymentKey, orderName: d.orderName, amount: d.totalAmount,
      method: (d.method || "") + (d.useEscrow ? " (에스크로)" : ""), approvedAt: d.approvedAt || new Date().toISOString(),
      receiptUrl: (d.receipt && d.receipt.url) || "", test: isTest, ...ship,
    }).catch((e) => console.error("order save failed", d.orderId, e && e.message)));
  }
  if (env.ORDER_MAIL) {
    after.push(sendMail(env, orderMail(env, d, ship, isTest)).catch((e) => console.error("order mail failed", d.orderId, e && e.message)));
  }
  if (after.length) {
    const all = Promise.all(after);
    if (ctx && ctx.waitUntil) ctx.waitUntil(all); else await all;
  }
  return json({
    orderId: d.orderId, orderName: d.orderName, totalAmount: d.totalAmount, method: d.method,
    approvedAt: d.approvedAt, receiptUrl: d.receipt && d.receipt.url, status: d.status, isTest,
  });
}

/* ---------------- admin ---------------- */

const enc = new TextEncoder();
const b64url = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function sign(env, msg) {
  const key = await crypto.subtle.importKey("raw", enc.encode("grazr-admin:" + env.ADMIN_PASSWORD), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
}

async function sameSecret(a, b) {
  const [x, y] = await Promise.all([crypto.subtle.digest("SHA-256", enc.encode(a)), crypto.subtle.digest("SHA-256", enc.encode(b))]);
  return crypto.subtle.timingSafeEqual(x, y);
}

async function session(request, env) {
  const m = /(?:^|;\s*)gz_admin=([^;]+)/.exec(request.headers.get("Cookie") || "");
  if (!m) return false;
  const [exp, sig] = m[1].split(".");
  if (!exp || !sig || Number(exp) * 1000 < Date.now()) return false;
  return sameSecret(sig, await sign(env, "admin:" + exp));
}

const cookie = (value, maxAge) => `gz_admin=${value}; Path=/api/admin; HttpOnly; Secure; SameSite=Strict; Max-Age=${maxAge}`;

async function admin(request, env, url) {
  if (!env.ADMIN_PASSWORD) return json({ message: "관리자 비밀번호(ADMIN_PASSWORD)가 아직 설정되지 않았습니다." }, 503);
  if (!env.ORDERS) return json({ message: "주문 저장소(ORDERS)가 설정되지 않았습니다." }, 503);
  const path = url.pathname.slice("/api/admin".length);
  const post = request.method === "POST";
  if (post) {
    // same-site JSON only (blocks cross-site form posts)
    const origin = request.headers.get("Origin");
    if ((origin && origin !== url.origin) || !(request.headers.get("Content-Type") || "").includes("application/json"))
      return json({ message: "허용되지 않은 요청입니다." }, 403);
  }
  const db = store(env);
  const body = post ? await request.json().catch(() => ({})) : {};

  if (path === "/login" && post) {
    if (!(await db.loginAllowed())) return json({ message: "비밀번호를 여러 번 틀렸습니다. 15분 뒤에 다시 시도하세요." }, 429);
    if (typeof body.password !== "string" || !(await sameSecret(body.password, env.ADMIN_PASSWORD))) {
      await db.loginFailed();
      return json({ message: "비밀번호가 맞지 않습니다." }, 401);
    }
    const exp = Math.floor(Date.now() / 1000) + SESSION_S;
    return json({ ok: true }, 200, { "Set-Cookie": cookie(exp + "." + (await sign(env, "admin:" + exp)), SESSION_S) });
  }
  if (path === "/logout" && post) return json({ ok: true }, 200, { "Set-Cookie": cookie("", 0) });
  if (!(await session(request, env))) return json({ message: "로그인이 필요합니다." }, 401);

  if (path === "/orders" && request.method === "GET") {
    return json({ ...(await db.list(url.searchParams.get("status") || "paid")), couriers: COURIERS, live: !env.TOSS_SECRET_KEY?.startsWith("test_") });
  }
  const m = /^\/orders\/([A-Za-z0-9_-]{6,64})\/(ship|unship|note|sync|cancel)$/.exec(path);
  if (!m || !post) return json({ message: "없는 주소입니다." }, 404);
  const [, id, action] = m;
  const order = await db.get(id);
  if (!order) return json({ message: "주문을 찾을 수 없습니다." }, 404);

  if (action === "ship") {
    const tracking = String(body.tracking || "").replace(/[^0-9A-Za-z-]/g, "").slice(0, 30);
    const courier = COURIERS[body.courier] ? body.courier : "logen";
    if (tracking.length < 6) return json({ message: "송장번호를 확인해 주세요." }, 400);
    if (order.status === "canceled") return json({ message: "취소된 주문입니다." }, 400);
    return json({ order: await db.ship(id, courier, tracking) });
  }
  if (action === "unship") return json({ order: await db.unship(id) });
  if (action === "note") return json({ order: await db.setNote(id, clip(String(body.note || ""), 500)) });

  if (!env.TOSS_SECRET_KEY) return json({ message: "토스페이먼츠 키가 설정되지 않았습니다." }, 500);
  if (action === "sync") {
    const r = await fetch(TOSS + "/" + encodeURIComponent(order.paymentKey), { headers: { Authorization: tossAuth(env) } });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return json({ message: d.message || "토스페이먼츠 조회에 실패했습니다." }, 502);
    const next = d.status === "CANCELED" ? "canceled" : order.status === "canceled" ? "paid" : order.status;
    const o = next !== order.status ? await db.setStatus(id, next) : order;
    return json({ order: o, toss: { status: d.status, balanceAmount: d.balanceAmount } });
  }
  // action === "cancel": full refund through Toss
  if (order.status === "canceled") return json({ message: "이미 취소된 주문입니다." }, 400);
  const reason = clip(String(body.reason || ""), 100) || "판매자 취소";
  const r = await fetch(TOSS + "/" + encodeURIComponent(order.paymentKey) + "/cancel", {
    method: "POST",
    headers: { Authorization: tossAuth(env), "Content-Type": "application/json", "Idempotency-Key": "cancel-" + id },
    body: JSON.stringify({ cancelReason: reason }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok && d.code !== "ALREADY_CANCELED_PAYMENT") return json({ message: d.message || "결제 취소에 실패했습니다." }, 502);
  const o = await db.setStatus(id, "canceled");
  await db.setNote(id, (o.note ? o.note + "\n" : "") + "결제 취소: " + reason + " (" + kst() + ")");
  return json({ order: await db.get(id) });
}

/* ---------------- router ---------------- */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/api/confirm") return confirm(request, env, ctx);
    if (url.pathname.startsWith("/api/admin/")) return admin(request, env, url);
    if (url.pathname === "/api/mail-test") return mailTest(request, env, url);
    return env.ASSETS.fetch(request);
  },
};

export { orderMail };
