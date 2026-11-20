"""Build the GRAZR website into website/public (the folder Cloudflare serves).

  pip install jinja2 fonttools brotli
  python3 website/build.py

Text and facts: website/content.py (pages) and website/legal.py (이용약관, 개인정보처리방침).
Media: website/tools/make_media.py (writes website/public/media).
The fonts are cut down to the characters the pages use, so re-run this after any text change.
"""
import datetime
import hashlib
import html
import importlib.util
import json
import os
import re

from fontTools import subset
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "public")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = load("content")
L = load("legal")


def short_hash(data):
    return hashlib.sha1(data).hexdigest()[:10]


def todo(lang="ko"):
    return Markup('<span class="todo">%s</span>' % ("확인 필요" if lang == "ko" else "TBD"))


def val(x, lang="ko"):
    return todo(lang) if x is None else escape(x)


def fill_values():
    b, s = C.BUSINESS, C.SHIPPING
    return {
        "name": b["name"], "ceo": b["ceo"], "phone": b["phone"], "email": b["email"],
        "privacy_officer": b["privacy_officer"], "courier": s["courier"], "return_fee": s["return_fee"],
        "exchange_fee": s["exchange_fee"], "return_address": s["return_address"], "effective": C.TERMS_EFFECTIVE,
    }


def fill(text):
    """Escape a legal paragraph and drop in business values ({name} ...), marking missing ones."""
    vals = fill_values()
    out = escape(text)
    for k, v in vals.items():
        out = Markup(str(out).replace("{%s}" % k, str(val(v))))
    return out


def write(rel, text):
    path = os.path.join(PUB, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


FONTS = [  # family, weight, source
    ("Pretendard", 400, "Pretendard-Regular.woff2"),
    ("Pretendard", 600, "Pretendard-SemiBold.woff2"),
    ("Montserrat", 400, "Montserrat_400Regular.ttf"),
    ("Montserrat", 500, "Montserrat_500Medium.ttf"),
]


def build_fonts(text):
    """Subset each font to the characters used on the site; write fonts.css with hashed file names."""
    d = os.path.join(PUB, "assets", "fonts")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".woff2"):
            os.remove(os.path.join(d, f))
    chars = set(text) | set(chr(c) for c in range(0x20, 0x7F)) | set("·×°–—‘’“”…₩©")
    chars = {c for c in chars if ord(c) >= 0x20}
    css, preload = [], []
    for family, weight, src in FONTS:
        latin_only = family == "Montserrat"
        use = {c for c in chars if not latin_only or ord(c) < 0x2500}
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]
        opts.hinting = False
        opts.desubroutinize = True
        font = subset.load_font(os.path.join(HERE, "src", "fonts", src), opts)
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=[ord(c) for c in use])
        sub.subset(font)
        tmp = os.path.join(d, "tmp.woff2")
        subset.save_font(font, tmp, opts)
        data = open(tmp, "rb").read()
        name = "%s-%d.%s.woff2" % (family.lower(), weight, short_hash(data))
        os.replace(tmp, os.path.join(d, name))
        url = "/assets/fonts/" + name
        css.append('@font-face{font-family:"%s";font-style:normal;font-weight:%d;font-display:swap;'
                   'src:url(%s) format("woff2")}' % (family, weight, url))
        if weight in (400,):
            preload.append(url)
        print("font %-10s %d  %4d KB" % (family, weight, len(data) // 1024))
    write("assets/css/fonts.css", "\n".join(css) + "\n")
    return preload


def jsonld():
    data = {
        "@context": "https://schema.org", "@type": "Product", "name": "GRAZR DP-301 퍼터",
        "brand": {"@type": "Brand", "name": "GRAZR"}, "model": "DP-301", "description": C.KO["description"],
        "offers": {"@type": "Offer", "priceCurrency": "KRW", "price": str(C.PRICE_KRW),
                   "availability": "https://schema.org/InStock", "itemCondition": "https://schema.org/NewCondition",
                   "url": C.STORE_URL,
                   # same terms as content.SHIPPING: free shipping in Korea, dispatched within 1 day
                   "shippingDetails": {
                       "@type": "OfferShippingDetails",
                       "shippingRate": {"@type": "MonetaryAmount", "value": 0, "currency": "KRW"},
                       "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "KR"},
                       "deliveryTime": {
                           "@type": "ShippingDeliveryTime",
                           "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "DAY"},
                           "transitTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 3, "unitCode": "DAY"},
                       },
                   },
                   # 7-day returns by mail; change of mind: buyer pays 16,000 KRW round trip (free outbound), defects: free
                   "hasMerchantReturnPolicy": {
                       "@type": "MerchantReturnPolicy",
                       "applicableCountry": "KR",
                       "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                       "merchantReturnDays": 7,
                       "returnMethod": "https://schema.org/ReturnByMail",
                       "customerRemorseReturnFees": "https://schema.org/ReturnShippingFees",
                       "customerRemorseReturnShippingFeesAmount": {"@type": "MonetaryAmount", "value": 16000, "currency": "KRW"},
                       "itemDefectReturnFees": "https://schema.org/FreeReturn",
                   }},
    }
    if C.SITE_URL:
        data["image"] = [C.SITE_URL + "/media/og.jpg", C.SITE_URL + "/media/product/full-black.webp"]
        data["url"] = C.SITE_URL + "/"
    org = {"@context": "https://schema.org", "@type": "Organization", "name": "GRAZR", "alternateName": "그레이저",
           "sameAs": [C.INSTAGRAM_URL, C.YOUTUBE_URL, C.KAKAO_URL]}
    if C.SITE_URL:
        org["url"] = C.SITE_URL + "/"
        org["logo"] = C.SITE_URL + "/assets/img/logo-stacked.png"
    return json.dumps([data, org], ensure_ascii=False)


def main():
    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    hero_frames = len([f for f in os.listdir(os.path.join(PUB, "media", "hero", "1600")) if f.endswith(".webp")])
    common = dict(site_url=C.SITE_URL, store_url=C.STORE_URL, youtube_url=C.YOUTUBE_URL, kakao_url=C.KAKAO_URL, instagram_url=C.INSTAGRAM_URL, kakao_chat_url=C.KAKAO_CHAT_URL, biz=C.BUSINESS,
                  options=C.OPTIONS, shipping=C.SHIPPING, notice=C.NOTICE, direct_pay=C.DIRECT_PAY,
                  hero_frames=hero_frames, year=datetime.date.today().year, fill=fill,
                  price=C.PRICE_KRW, pay_mode=C.PAY_MODE, toss_client_key=C.TOSS_CLIENT_KEY)

    def render_all(preload, v):
        pages = []
        for t, path, rel, extra in (
            (C.KO, "/", "index.html", {"jsonld": jsonld()}),
            (C.EN, "/en/", "en/index.html", {}),
            (C.KO, "/terms/", "terms/index.html", {"page_title": L.TERMS_TITLE, "intro": L.TERMS_INTRO, "sections": L.TERMS}),
            (C.KO, "/privacy/", "privacy/index.html",
             {"page_title": L.PRIVACY_TITLE, "intro": L.PRIVACY_INTRO, "sections": L.PRIVACY}),
            (C.KO, "/404", "404.html", {}),
            (C.KO, "/checkout/", "checkout/index.html", {"tpl": "checkout.html", "noindex": True}),
            (C.KO, "/checkout/success/", "checkout/success/index.html",
             {"tpl": "checkout_result.html", "noindex": True, "result": "success"}),
            (C.KO, "/checkout/fail/", "checkout/fail/index.html",
             {"tpl": "checkout_result.html", "noindex": True, "result": "fail"}),
        ):
            tpl = extra.get("tpl") or ("index.html" if rel.endswith("index.html") and "page_title" not in extra else
                                       ("legal.html" if "page_title" in extra else "404.html"))
            lang = t["lang"]
            ctx = dict(common, **extra, t=t, path=path, v=v, preload_fonts=preload,
                       val=lambda x, _l=lang: val(x, _l))
            pages.append((rel, env.get_template(tpl).render(**ctx)))
        return pages

    # pass 1 renders the text so the fonts can be subset; pass 2 writes pages with the final font URLs
    css = open(os.path.join(PUB, "assets", "css", "site.css"), "rb").read()
    js = open(os.path.join(PUB, "assets", "js", "site.js"), "rb").read()
    co = open(os.path.join(PUB, "assets", "js", "checkout.js"), "rb").read()
    first = render_all([], {"css": "", "js": "", "fonts": "", "co": ""})
    text = html.unescape("".join(p for _, p in first))
    preload = build_fonts(text)
    fonts_css = open(os.path.join(PUB, "assets", "css", "fonts.css"), "rb").read()
    v = {"css": short_hash(css), "js": short_hash(js), "fonts": short_hash(fonts_css), "co": short_hash(co)}
    for rel, page in render_all(preload, v):
        write(rel, re.sub(r"\n\s*\n+", "\n", page))
        print("page", rel)

    write("site.webmanifest", json.dumps({
        "name": "GRAZR", "short_name": "GRAZR", "start_url": "/", "display": "standalone",
        "background_color": "#000000", "theme_color": "#000000",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]}, indent=1))
    robots = "User-agent: *\nAllow: /\n"
    if C.SITE_URL:
        robots += "Sitemap: %s/sitemap.xml\n" % C.SITE_URL
        urls = "".join("<url><loc>%s%s</loc></url>" % (C.SITE_URL, p) for p in ("/", "/en/", "/terms/", "/privacy/"))
        write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n' % urls)
    write("robots.txt", robots)
    write("_headers", "\n".join([
        "/*",
        "  X-Content-Type-Options: nosniff",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "/assets/fonts/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "/assets/*",
        "  Cache-Control: public, max-age=604800",
        "/media/*",
        "  Cache-Control: public, max-age=604800",
        "",
    ]))
    print("done")


if __name__ == "__main__":
    main()
