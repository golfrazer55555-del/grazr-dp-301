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


# /media/* is cached for a week, so a file regenerated under the same name (a new 3D model, a re-rendered
# photo) would keep showing the old copy. Every /media/ URL in the pages gets ?v=<content hash> instead.
MEDIA_URL = re.compile(r"/media/[A-Za-z0-9_./-]+\.(?:webp|jpe?g|png|glb|gltf|usdz|mp4|webm|svg)(?![A-Za-z0-9_?])")
_media_v = {}


def media_version(m):
    url = m.group(0)
    path = os.path.join(PUB, url.lstrip("/"))
    if not os.path.isfile(path):
        return url
    if url not in _media_v:
        with open(path, "rb") as f:
            _media_v[url] = short_hash(f.read())[:8]
    return url + "?v=" + _media_v[url]


def todo(lang="ko"):
    return Markup('<span class="todo">%s</span>' % ("확인 필요" if lang == "ko" else "TBD"))


def val(x, lang="ko"):
    return todo(lang) if x is None else escape(x)


def fill_values():
    b, s = C.BUSINESS, C.SHIPPING
    return {
        "name": b["name"], "ceo": b["ceo"], "phone": b["phone"], "email": b["email"],
        "privacy_officer": b["privacy_officer"], "courier": s["courier"], "return_fee": s["return_fee"],
        "exchange_fee": s["exchange_fee"], "return_address": s["return_address"], "effective": C.TERMS_EFFECTIVE, "revised": C.PRIVACY_REVISED,
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


def jsonld(key=None):
    """Product (+ Organization) structured data. key=None: organization only (home page)."""
    org = {"@context": "https://schema.org", "@type": "Organization", "name": "GRAZR", "alternateName": "그레이저",
           "sameAs": [C.INSTAGRAM_URL, C.YOUTUBE_URL, C.KAKAO_URL]}
    if C.SITE_URL:
        org["url"] = C.SITE_URL + "/"
        org["logo"] = C.SITE_URL + "/assets/img/logo-stacked.png"
    if key is None:
        return json.dumps([org], ensure_ascii=False)
    p = C.PRODUCTS[key]
    desc = C.KO["description"] if key == "dp-301" else C.P501["description"]
    images = ["/media/og.jpg", "/media/product/full-black.webp"] if key == "dp-301" else ["/media/dp501/og.jpg", "/media/dp501/full.webp"]
    data = {
        "@context": "https://schema.org", "@type": "Product", "name": p["name"],
        "brand": {"@type": "Brand", "name": "GRAZR"}, "model": key.upper(), "description": desc,
        "offers": {"@type": "Offer", "priceCurrency": "KRW", "price": str(p["price"]),
                   "availability": "https://schema.org/InStock", "itemCondition": "https://schema.org/NewCondition",
                   "url": (C.SITE_URL + p["page"]) if C.SITE_URL else p["store"],
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
                   # 7-day returns by mail; change of mind: buyer pays 12,000 KRW round trip (free outbound), defects: free
                   "hasMerchantReturnPolicy": {
                       "@type": "MerchantReturnPolicy",
                       "applicableCountry": "KR",
                       "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                       "merchantReturnDays": 7,
                       "returnMethod": "https://schema.org/ReturnByMail",
                       "customerRemorseReturnFees": "https://schema.org/ReturnShippingFees",
                       "customerRemorseReturnShippingFeesAmount": {"@type": "MonetaryAmount", "value": 12000, "currency": "KRW"},
                       "itemDefectReturnFees": "https://schema.org/FreeReturn",
                   }},
    }
    if C.SITE_URL:
        data["image"] = [C.SITE_URL + i for i in images]
        data["url"] = C.SITE_URL + p["page"]
    return json.dumps([data, org], ensure_ascii=False)


def main():
    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    hero_frames = len([f for f in os.listdir(os.path.join(PUB, "media", "hero", "1600")) if f.endswith(".webp")])
    # DP-501 scroll hero: frames are fetched by site.js, so their version tag comes from here
    h501 = os.path.join(PUB, "media", "dp501", "hero")
    hero501_frames = len([f for f in os.listdir(os.path.join(h501, "1600")) if f.endswith(".webp")])
    hsum = hashlib.sha1()
    for d in sorted(os.listdir(h501)):
        for f in sorted(os.listdir(os.path.join(h501, d))):
            with open(os.path.join(h501, d, f), "rb") as fh:
                hsum.update(fh.read())
    common = dict(site_url=C.SITE_URL, store_url=C.STORE_URL, youtube_url=C.YOUTUBE_URL, kakao_url=C.KAKAO_URL, instagram_url=C.INSTAGRAM_URL, kakao_chat_url=C.KAKAO_CHAT_URL, biz=C.BUSINESS,
                  options=C.OPTIONS, shipping=C.SHIPPING, notice=C.NOTICE, direct_pay=C.DIRECT_PAY,
                  hero_frames=hero_frames, year=datetime.date.today().year, fill=fill,
                  price=C.PRICE_KRW, pay_mode=C.PAY_MODE, toss_client_key=C.TOSS_CLIENT_KEY, products=C.PRODUCTS,
                  ga_id=C.GA_ID, hero501_frames=hero501_frames, hero501_v=hsum.hexdigest()[:8])

    def render_all(preload, v):
        pages = []
        if C.SHOW_DP501:
            product_pages = (
                (C.KO, "/", "index.html", {"tpl": "home.html", "jsonld": jsonld()}),
                (C.KO, "/dp-301/", "dp-301/index.html", {"tpl": "index.html", "jsonld": jsonld("dp-301")}),
                (C.KO, "/dp-501/", "dp-501/index.html",
                 {"tpl": "dp501.html", "jsonld": jsonld("dp-501"), "p": C.P501, "notice": C.NOTICE_501,
                  "product": C.PRODUCTS["dp-501"], "store_url": C.STORE_URL_501}),
                (C.KO, "/checkout/dp-501/", "checkout/dp-501/index.html",
                 {"tpl": "checkout.html", "noindex": True, "product": C.PRODUCTS["dp-501"]}),
            )
        else:
            product_pages = ((C.KO, "/", "index.html", {"tpl": "index.html", "jsonld": jsonld("dp-301")}),)
        for t, path, rel, extra in product_pages + (
            (C.EN, "/en/", "en/index.html", {}),
            (C.KO, "/terms/", "terms/index.html", {"page_title": L.TERMS_TITLE, "intro": L.TERMS_INTRO, "sections": L.TERMS}),
            (C.KO, "/privacy/", "privacy/index.html",
             {"page_title": L.PRIVACY_TITLE, "intro": L.PRIVACY_INTRO, "sections": L.PRIVACY}),
            (C.KO, "/404", "404.html", {}),
            (C.KO, "/checkout/", "checkout/index.html",
             {"tpl": "checkout.html", "noindex": True, "product": C.PRODUCTS["dp-301"]}),
            (C.KO, "/checkout/success/", "checkout/success/index.html",
             {"tpl": "checkout_result.html", "noindex": True, "result": "success"}),
            (C.KO, "/checkout/fail/", "checkout/fail/index.html",
             {"tpl": "checkout_result.html", "noindex": True, "result": "fail"}),
            # putting game (prototype: not linked from the site, not indexed)
            (C.KO, "/game/", "game/index.html", {"tpl": "game.html", "noindex": True}),
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
    game_js = open(os.path.join(PUB, "game", "game.js"), "rb").read()
    game_css = open(os.path.join(PUB, "game", "game.css"), "rb").read()
    first = render_all([], {"css": "", "js": "", "fonts": "", "co": "", "game": "", "gcss": ""})
    # the game writes its HUD text from JS: its characters go into the font subset too
    text = html.unescape("".join(p for _, p in first)) + game_js.decode("utf-8") + game_css.decode("utf-8")
    preload = build_fonts(text)
    fonts_css = open(os.path.join(PUB, "assets", "css", "fonts.css"), "rb").read()
    v = {"css": short_hash(css), "js": short_hash(js), "fonts": short_hash(fonts_css), "co": short_hash(co),
         "game": short_hash(game_js), "gcss": short_hash(game_css)}
    for rel, page in render_all(preload, v):
        write(rel, MEDIA_URL.sub(media_version, re.sub(r"\n\s*\n+", "\n", page)))
        print("page", rel)

    write("site.webmanifest", json.dumps({
        "name": "GRAZR", "short_name": "GRAZR", "start_url": "/", "display": "standalone",
        "background_color": "#000000", "theme_color": "#000000",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]}, indent=1))
    robots = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /checkout/\n"
    if C.SITE_URL:
        robots += "Sitemap: %s/sitemap.xml\n" % C.SITE_URL
        urls = "".join("<url><loc>%s%s</loc></url>" % (C.SITE_URL, p) for p in (("/", "/dp-301/", "/dp-501/") if C.SHOW_DP501 else ("/",)) + ("/en/", "/terms/", "/privacy/"))
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
        "/admin/*",
        "  X-Robots-Tag: noindex, nofollow",
        "  Cache-Control: no-store",
        "  X-Frame-Options: DENY",
        "  Referrer-Policy: no-referrer",
        "",
    ]))
    print("done")


if __name__ == "__main__":
    main()
