"""
=============================================================
  AI COUPON FINDER — SCRAPER ENGINE v4
  Sources (priority order):
    1. User-imported datasets (CSV / JSON from file or URL)
    2. Extended coupon_database.json (120+ stores, 700+ codes)
    3. REAL-TIME: CouponFollow, Promocodes.in, TimesVoucher (plain HTML)
    4. Indian sources: CouponDunia, GrabOn, CashKaro, Desidime, Savee.in
    5. International fallback: RetailMeNot, Slickdeals
    6. Code Verification: live ping to confirm codes are still active
    7. Generic fallback codes
=============================================================
"""

import re, time, random, requests, urllib.parse, json, os, csv, io
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path

# ─── DOTENV LOADER ───────────────────────────────────────────────
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; fall back to OS env vars

# ─── PATHS ────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
DB_FILE     = DATA_DIR / "coupon_database.json"
IMPORT_DIR  = DATA_DIR / "imports"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)

# ─── HTTP HEADERS ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
    "DNT": "1",
}
TIMEOUT = 12

# ─── PLACEHOLDER / INVALID CODE PATTERNS ─────────────────────
# Codes scraped from JS-gated sites come as these strings.
# We filter them out and label such coupons as "Visit Site" deals.
INVALID_CODES = {
    "CLICK TO REVEAL", "CLICK TO SHOW", "REVEAL CODE", "SHOW CODE",
    "SEE LINK", "SEE GOOGLE", "CHECK LINK", "NO CODE NEEDED",
    "ACTIVATE DEAL", "GET DEAL", "SHOP NOW", "SEE SITE",
    "GET CODE", "VIEW CODE", "UNLOCK CODE", "VERIFIED",
}

def _is_valid_code(code: str) -> bool:
    """Return True only if code is a real alphanumeric coupon code."""
    if not code or not code.strip():
        return False
    c = code.strip().upper()
    if c in INVALID_CODES:
        return False
    # Must be 3-20 chars, only letters/digits/hyphens, no spaces
    if " " in c or len(c) < 3 or len(c) > 22:
        return False
    if not re.match(r'^[A-Z0-9][A-Z0-9\-_]{2,21}$', c):
        return False
    return True


# ─── SCOPE DETECTION ──────────────────────────────────────────
# Classify a coupon as Sitewide, Category-wide, or Product Specific.

_SITEWIDE_KW  = ["sitewide", "entire purchase", "everything", "any order",
                  "all orders", "all items", "all products", "online order",
                  "any item", "new user", "new customer", "first order",
                  "new members", "students", "members only", "app orders"]
_PRODUCT_KW   = ["macbook", "iphone", "ipad", "galaxy s", "airpods",
                  "ps5", "xbox", "pixel", "oled", "thinkpad", "spectre",
                  "zinger", "big mac", "whopper", "footlong", "cheesy bread",
                  "air max", "ultraboost", "yeezy", "dunk", "jordan"]

def _detect_scope(title: str) -> str:
    """Return 'Sitewide', 'Category', or 'Product Specific'."""
    t = title.lower()
    if any(k in t for k in _PRODUCT_KW):
        return "Product Specific"
    if any(k in t for k in _SITEWIDE_KW):
        return "Sitewide"
    # Category-level heuristics: off + category noun
    if re.search(r'off\s+(electronics|fashion|shoes|clothing|food|travel|beauty|gaming|furniture|grocery|books|pets|sports|appliances|phones|laptops|tvs|cameras)', t):
        return "Category"
    return "Sitewide"  # default for store-level deals

# ─── STORE ALIASES ────────────────────────────────────────────
STORE_ALIASES = {
    "amazon.com": "amazon", "amazon.in": "amazon-in",
    "nike.com": "nike", "adidas.com": "adidas", "puma.com": "puma",
    "walmart.com": "walmart", "target.com": "target", "costco.com": "costco",
    "bestbuy.com": "best-buy", "best buy": "best-buy",
    "ebay.com": "ebay", "etsy.com": "etsy", "apple.com": "apple",
    "samsung.com": "samsung", "zara.com": "zara", "hm.com": "h-m",
    "h&m": "h-m", "asos.com": "asos", "shein.com": "shein",
    "aliexpress.com": "aliexpress", "flipkart.com": "flipkart",
    "myntra.com": "myntra", "swiggy.com": "swiggy", "zomato.com": "zomato",
    "nykaa.com": "nykaa", "dominos.com": "dominos", "domino's": "dominos",
    "pizzahut.com": "pizza-hut", "pizza hut": "pizza-hut",
    "booking.com": "booking-com", "expedia.com": "expedia",
    "airbnb.com": "airbnb", "sephora.com": "sephora",
    "gap.com": "gap", "oldnavy.com": "old-navy", "old navy": "old-navy",
    "ubereats.com": "uber-eats", "uber eats": "uber-eats",
    "instacart.com": "instacart", "chewy.com": "chewy",
    "wayfair.com": "wayfair", "ikea.com": "ikea",
    "aliexpress.com": "aliexpress", "temu.com": "temu",
    "meesho.com": "meesho", "blinkit.com": "blinkit",
    "bigbasket.com": "bigbasket", "lenskart.com": "lenskart",
    "ajio.com": "ajio", "snapdeal.com": "snapdeal", "croma.com": "croma",
    "makemytrip.com": "makemytrip", "mmt.com": "mmt", "ixigo.com": "ixigo",
    "paytm.com": "paytm", "ola.com": "ola", "uber.com": "uber",
    "netflix.com": "netflix", "spotify.com": "spotify", "steam": "steam",
    "steampowered.com": "steam", "udemy.com": "udemy",
    "coursera.org": "coursera", "skillshare.com": "skillshare",
    "grubhub.com": "grubhub", "doordash.com": "doordash",
    "starbucks.com": "starbucks", "mcdonalds.com": "mcdonalds",
    "subway.com": "subway", "kfc.com": "kfc",
    "dell.com": "dell", "hp.com": "hp", "lenovo.com": "lenovo",
    "sony.com": "sony", "lg.com": "lg", "dyson.com": "dyson",
    "gopro.com": "gopro", "garmin.com": "garmin",
    "overstock.com": "overstock", "groupon.com": "groupon",
    "rakuten.com": "rakuten", "shopback.com": "shopback",
    "macys.com": "macys", "nordstrom.com": "nordstrom",
    "kohls.com": "kohls", "walgreens.com": "walgreens", "cvs.com": "cvs",
    "wholefoods.com": "whole-foods", "wholefoodsmarket.com": "whole-foods",
    "lululemon.com": "lululemon", "reebok.com": "reebok",
    "underarmour.com": "under-armour", "under armour": "under-armour",
    "skechers.com": "skechers", "anthropologie.com": "anthropologie",
    "ebay.co.uk": "ebay", "amazon.co.uk": "amazon",
}

GENERIC_COUPONS = [
    {"title": "10% off Sitewide", "code": "SAVE10", "discount_value": 10, "discount_type": "Percentage", "category": "General"},
    {"title": "15% off First Purchase", "code": "FIRST15", "discount_value": 15, "discount_type": "Percentage", "category": "General"},
    {"title": "Free Shipping on orders ₹1999+", "code": "FREESHIP1999", "discount_value": 7, "discount_type": "Free Shipping", "category": "General"},
    {"title": "20% off for New Users", "code": "NEW20", "discount_value": 20, "discount_type": "Percentage", "category": "General"},
    {"title": "₹500 off ₹2000+ order", "code": "DEAL500", "discount_value": 500, "discount_type": "Flat Amount", "category": "General"},
    {"title": "5% Cashback on All Orders", "code": "CASH5", "discount_value": 5, "discount_type": "Cashback", "category": "General"},
    {"title": "25% off Weekend Flash Sale", "code": "WKND25", "discount_value": 25, "discount_type": "Percentage", "category": "General"},
    {"title": "Buy 2 Get 1 Free", "code": "B2G1FREE", "discount_value": 33, "discount_type": "Buy1Get1", "category": "General"},
    {"title": "30% off Clearance Items", "code": "CLEAR30", "discount_value": 30, "discount_type": "Percentage", "category": "General"},
    {"title": "Extra 12% off via App", "code": "APP12", "discount_value": 12, "discount_type": "Percentage", "category": "General"},
]


# ══════════════════════════════════════════════════════════════
#  NORMALISE STORE
# ══════════════════════════════════════════════════════════════

def normalize_store(url_or_name: str) -> tuple[str, str]:
    """Extract store slug + display name from a URL or plain store name.

    Handles:
      - Plain names:  "amazon", "Nike", "zomato"
      - Domain URLs:  "amazon.in", "www.flipkart.com"
      - Product URLs: "https://www.amazon.in/dp/B09XYZ/ref=sr_1_1?ie=UTF8"
                      "https://www.myntra.com/shirts/nike/12345"
    """
    raw = url_or_name.strip().lower()

    # Strip protocol
    raw = re.sub(r"^https?://", "", raw)

    # Extract only the hostname (everything before first /)
    host = raw.split("/")[0]
    host = re.sub(r"^www\.", "", host)      # remove www.
    host = re.sub(r"^m\.", "", host)         # remove m. (mobile subdomains)

    # Check alias map with the clean hostname
    slug = STORE_ALIASES.get(host)

    if not slug:
        # If it's a domain, use the part before the first dot as slug
        if "." in host:
            slug = host.split(".")[0]
        else:
            # Plain text name — normalise spaces to hyphens
            slug = host.replace(" ", "-")

    # Clean slug: lowercase, only alphanum and hyphens
    slug = re.sub(r"[^a-z0-9\-]", "", slug)

    display = slug.replace("-", " ").replace("_", " ").title()
    return slug, display



# ══════════════════════════════════════════════════════════════
#  SOURCE 1 — EXTENDED COUPON DATABASE (JSON)
# ══════════════════════════════════════════════════════════════

_DB_CACHE: dict | None = None

def _load_database() -> dict:
    global _DB_CACHE
    if _DB_CACHE is None:
        try:
            with open(DB_FILE, encoding="utf-8-sig") as f:  # utf-8-sig strips BOM if present
                _DB_CACHE = json.load(f)
        except Exception as e:
            print(f"[DB] Failed to load coupon_database.json: {e}")
            _DB_CACHE = {}
    return _DB_CACHE


def get_from_database(slug: str) -> list[dict]:
    db   = _load_database()
    rows = db.get(slug, db.get(slug.replace("-", ""), []))

    # Fuzzy match: try partial slug
    if not rows:
        for key, val in db.items():
            if key.startswith(slug[:4]) or slug[:4] in key:
                rows = val
                break

    # Do NOT fall back to generic codes — they are 100% fake
    if not rows:
        return []

    result = []
    for c in rows:
        if c.get("_meta"):
            continue
        code  = str(c.get("code", "")).strip()
        valid = _is_valid_code(code)
        result.append({
            "title"         : c.get("title", "") + " (may be expired)",
            "code"          : code.upper() if valid else "",
            "has_code"      : valid,
            "discount_value": float(c.get("discount_value", 10)),
            "discount_type" : c.get("discount_type", "Percentage"),
            "category"      : c.get("category", "General"),
            "scope"         : _detect_scope(c.get("title", "")),
            "source"        : "Coupon DB",
            "source_url"    : f"https://{slug.replace('-', '')}.com",
            "verified"      : False,  # DB codes are NEVER verified — they may be expired
            "historical"    : True,   # flag: show with warning badge in UI
        })
    return result


# ══════════════════════════════════════════════════════════════
#  SOURCE 2 — USER-IMPORTED DATASETS
#  Supports: JSON, CSV  •  from local file OR remote URL
# ══════════════════════════════════════════════════════════════

_IMPORT_CACHE: list[dict] | None = None

def reload_imports() -> list[dict]:
    """Reload all files from data/imports/ and merge into a flat list."""
    global _IMPORT_CACHE
    all_coupons = []
    for fp in IMPORT_DIR.iterdir():
        try:
            if fp.suffix.lower() == ".json":
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    all_coupons.extend(data)
                elif isinstance(data, dict):
                    for store_coupons in data.values():
                        if isinstance(store_coupons, list):
                            all_coupons.extend(store_coupons)
            elif fp.suffix.lower() == ".csv":
                with open(fp, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        all_coupons.append(dict(row))
        except Exception as e:
            print(f"[Import] Error reading {fp.name}: {e}")
    _IMPORT_CACHE = all_coupons
    return all_coupons


def get_from_imports(slug: str, display: str) -> list[dict]:
    """Filter user-imported coupons for this store."""
    global _IMPORT_CACHE
    if _IMPORT_CACHE is None:
        reload_imports()

    results = []
    kw = display.lower().split()[0]  # first word of store name
    for c in (_IMPORT_CACHE or []):
        store_field = str(c.get("store", c.get("brand", c.get("platform", "")))).lower()
        title_field = str(c.get("title", c.get("description", ""))).lower()
        if not (kw in store_field or kw in title_field or slug in store_field):
            continue
        raw_code = str(c.get("code", c.get("coupon_code", ""))).strip()
        valid    = _is_valid_code(raw_code)
        title    = str(c.get("title", c.get("description", "Unknown Coupon")))[:120]
        results.append({
            "title"         : title,
            "code"          : raw_code.upper() if valid else "",
            "has_code"      : valid,
            "discount_value": float(c.get("discount_value", c.get("discount_pct", 10)) or 10),
            "discount_type" : str(c.get("discount_type", "Percentage")),
            "category"      : str(c.get("category", "General")),
            "scope"         : _detect_scope(title),
            "source"        : "Imported Dataset",
            "source_url"    : str(c.get("source_url", c.get("url", "#"))),
            "verified"      : valid,
        })
    return results


def import_from_url(url: str, filename: str = None) -> dict:
    """
    Download a JSON or CSV dataset from any URL and save to data/imports/.
    Returns: {"status": "ok"|"error", "count": int, "filename": str, "message": str}
    """
    global _IMPORT_CACHE
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return {"status": "error", "message": f"HTTP {resp.status_code}"}

        content_type = resp.headers.get("Content-Type", "")
        raw = resp.text

        # Auto-detect format
        if url.endswith(".csv") or "csv" in content_type:
            ext = ".csv"
        else:
            ext = ".json"

        if not filename:
            from urllib.parse import urlparse
            filename = urlparse(url).path.split("/")[-1] or "imported"
            if not filename.endswith(ext):
                filename += ext

        save_path = IMPORT_DIR / filename
        save_path.write_text(raw, encoding="utf-8")

        # Count entries
        count = 0
        if ext == ".json":
            data = json.loads(raw)
            if isinstance(data, list):
                count = len(data)
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        count += len(v)
        else:
            count = raw.count("\n") - 1  # rough CSV row count

        _IMPORT_CACHE = None  # force reload
        reload_imports()

        return {"status": "ok", "count": count, "filename": filename,
                "message": f"Imported {count} records from {url}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def import_from_upload(file_content: bytes, filename: str) -> dict:
    """
    Save an uploaded file (bytes) to data/imports/.
    Returns: {"status", "count", "filename", "message"}
    """
    global _IMPORT_CACHE
    try:
        save_path = IMPORT_DIR / filename
        save_path.write_bytes(file_content)

        count = 0
        text = file_content.decode("utf-8", errors="ignore")
        if filename.endswith(".json"):
            data = json.loads(text)
            count = len(data) if isinstance(data, list) else sum(len(v) for v in data.values() if isinstance(v, list))
        else:
            count = text.count("\n") - 1

        _IMPORT_CACHE = None
        reload_imports()

        return {"status": "ok", "count": count, "filename": filename,
                "message": f"Uploaded '{filename}' with {count} records"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_imports() -> list[dict]:
    """List all imported datasets with metadata."""
    files = []
    for fp in IMPORT_DIR.iterdir():
        if fp.suffix in [".json", ".csv"]:
            try:
                stat   = fp.stat()
                text   = fp.read_text(encoding="utf-8", errors="ignore")
                count  = 0
                if fp.suffix == ".json":
                    data  = json.loads(text)
                    count = len(data) if isinstance(data, list) else sum(len(v) for v in data.values() if isinstance(v, list))
                else:
                    count = max(text.count("\n") - 1, 0)
                files.append({
                    "filename" : fp.name,
                    "size_kb"  : round(stat.st_size / 1024, 1),
                    "records"  : count,
                    "modified" : datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except Exception:
                pass
    return files


def delete_import(filename: str) -> dict:
    """Delete an imported dataset file."""
    try:
        fp = IMPORT_DIR / filename
        if fp.exists():
            fp.unlink()
            global _IMPORT_CACHE
            _IMPORT_CACHE = None
            reload_imports()
            return {"status": "ok", "message": f"Deleted {filename}"}
        return {"status": "error", "message": "File not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ══════════════════════════════════════════════════════════════
#  SOURCE 3 — LIVE WEB SCRAPERS
# ══════════════════════════════════════════════════════════════

def scrape_retailmenot(slug: str) -> list[dict]:
    url = f"https://www.retailmenot.com/view/{slug}.com"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
                if isinstance(data, list):
                    data = data[0]
                for o in (data.get("offers", []) or []):
                    title = o.get("name", o.get("description", ""))
                    code  = (o.get("serialNumber", "") or o.get("couponCode", "")).strip()
                    pct   = _extract_pct(title)
                    if not title:
                        continue
                    valid = _is_valid_code(code)
                    coupons.append({
                        "title"         : title[:120],
                        "code"          : code.upper() if valid else "",
                        "has_code"      : valid,
                        "discount_value": pct,
                        "discount_type" : "Percentage" if "%" in title else "Flat Amount",
                        "scope"         : _detect_scope(title),
                        "source"        : "RetailMeNot",
                        "source_url"    : url,
                        "verified"      : valid,
                    })
            except Exception:
                continue

        if not coupons:
            for card in soup.select("[class*='offer'], [class*='coupon'], article"):
                title_el = card.find(["h3", "h2", "strong", "p"])
                code_el  = card.find(attrs={"data-code": True}) or card.find(class_=re.compile(r"code"))
                title = title_el.get_text(strip=True) if title_el else ""
                raw_code = ""
                if code_el:
                    raw_code = code_el.get("data-code", "") or code_el.get_text(strip=True)
                if title and len(title) > 5:
                    pct   = _extract_pct(title)
                    valid = _is_valid_code(raw_code)
                    coupons.append({
                        "title"         : title[:120],
                        "code"          : raw_code.upper() if valid else "",
                        "has_code"      : valid,
                        "discount_value": pct,
                        "discount_type" : "Percentage" if pct > 0 else "Flat Amount",
                        "scope"         : _detect_scope(title),
                        "source"        : "RetailMeNot",
                        "source_url"    : url,
                        "verified"      : valid,
                    })
        return coupons[:15]
    except Exception as e:
        print(f"[RetailMeNot] {e}")
        return []


def scrape_dealnews_rss(display: str) -> list[dict]:
    url = "https://feeds.dealnews.com/dealnews/feeds/all.rss"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "xml")
        kw   = display.lower().replace("-", " ")
        for item in soup.find_all("item"):
            title    = item.find("title")
            title    = title.get_text(strip=True) if title else ""
            link_tag = item.find("link")
            link     = link_tag.get_text(strip=True) if link_tag else ""
            desc_tag = item.find("description")
            desc     = BeautifulSoup(desc_tag.get_text(), "lxml").get_text(strip=True) if desc_tag else ""
            if not (kw in title.lower() or kw in desc.lower()):
                continue
            pct      = _extract_pct(title + " " + desc)
            flat     = _extract_flat(title + " " + desc)
            raw_code = _extract_code(title + " " + desc)
            valid    = _is_valid_code(raw_code)
            # DealNews items are often automatic discounts (no code needed)
            coupons.append({
                "title"         : title[:120],
                "code"          : raw_code.upper() if valid else "",
                "has_code"      : valid,
                "discount_value": pct if pct > 0 else flat,
                "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope"         : _detect_scope(title),
                "source"        : "DealNews",
                "source_url"    : link,
                "verified"      : True,   # DealNews editorial — always legit
            })
        return coupons[:8]
    except Exception as e:
        print(f"[DealNews] {e}")
        return []


def scrape_slickdeals(slug: str, display: str) -> list[dict]:
    query = urllib.parse.quote(f"{display} promo code coupon")
    url   = f"https://slickdeals.net/newsearch.php?q={query}&searchin=forums"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        for result in soup.select("[class*='threadTitle'], [class*='resultTitle'], h3 a, .title a"):
            title = result.get_text(strip=True)
            href  = result.get("href", "")
            if len(title) < 8:
                continue
            kw = display.lower().split()[0]
            if kw not in title.lower() and slug.split("-")[0] not in title.lower():
                continue
            pct      = _extract_pct(title)
            flat     = _extract_flat(title)
            raw_code = _extract_code(title)
            valid    = _is_valid_code(raw_code)
            src_url  = f"https://slickdeals.net{href}" if href.startswith("/") else href
            coupons.append({
                "title"         : title[:120],
                "code"          : raw_code.upper() if valid else "",
                "has_code"      : valid,
                "discount_value": pct if pct > 0 else flat,
                "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope"         : _detect_scope(title),
                "source"        : "Slickdeals",
                "source_url"    : src_url,
                "verified"      : valid,   # only verified if code actually extracted
            })
        return coupons[:8]
    except Exception as e:
        print(f"[Slickdeals] {e}")
        return []


# ══════════════════════════════════════════════════════════════
#  SOURCE 3b — INDIAN COUPON SCRAPERS
# ══════════════════════════════════════════════════════════════

def scrape_coupondunia(slug: str, display: str) -> list[dict]:
    """Scrape CouponDunia — India's largest coupon aggregator."""
    store_slug = slug.replace("-", "")
    url = f"https://coupondunia.in/{store_slug}/"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        # JSON-LD structured data (best quality)
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
                if isinstance(data, list):
                    data = data[0]
                for o in (data.get("offers", []) or []):
                    title = o.get("name", o.get("description", ""))
                    code  = str(o.get("serialNumber", o.get("couponCode", ""))).strip()
                    if not title:
                        continue
                    pct   = _extract_pct(title)
                    flat  = _extract_flat(title)
                    valid = _is_valid_code(code)
                    coupons.append({
                        "title"         : title[:120],
                        "code"          : code.upper() if valid else "",
                        "has_code"      : valid,
                        "discount_value": pct if pct > 0 else flat,
                        "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                        "scope"         : _detect_scope(title),
                        "source"        : "CouponDunia",
                        "source_url"    : url,
                        "verified"      : valid,
                    })
            except Exception:
                continue

        # HTML card fallback
        if not coupons:
            for card in soup.select(
                "[class*='coupon'], [class*='offer'], [class*='deal'], article, .card"
            ):
                title_el = card.find(["h3", "h2", "h4", "strong", "span"], class_=re.compile(r"title|name|head", re.I))
                if not title_el:
                    title_el = card.find(["h3", "h2", "strong"])
                code_el  = (card.find(attrs={"data-code": True})
                            or card.find(class_=re.compile(r"code|coupon-code", re.I)))
                title    = title_el.get_text(strip=True) if title_el else ""
                raw_code = ""
                if code_el:
                    raw_code = (code_el.get("data-code")
                                or code_el.get("data-couponcode")
                                or code_el.get_text(strip=True))
                if not title or len(title) < 6:
                    continue
                pct   = _extract_pct(title)
                flat  = _extract_flat(title)
                valid = _is_valid_code(raw_code)
                coupons.append({
                    "title"         : title[:120],
                    "code"          : raw_code.upper() if valid else "",
                    "has_code"      : valid,
                    "discount_value": pct if pct > 0 else flat,
                    "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                    "scope"         : _detect_scope(title),
                    "source"        : "CouponDunia",
                    "source_url"    : url,
                    "verified"      : valid,
                })
        return coupons[:15]
    except Exception as e:
        print(f"[CouponDunia] {e}")
        return []


def scrape_grabon(slug: str, display: str) -> list[dict]:
    """Scrape GrabOn — popular Indian coupon & cashback site."""
    store_slug = slug.replace("-", "-")
    url = f"https://www.grabon.in/{store_slug}-coupons/"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        for card in soup.select(
            "[class*='coupon'], [class*='offer'], .g-coupon, .coupon-box, article"
        ):
            title_el = card.find(["h3", "h2", "h4", "strong"],
                                  class_=re.compile(r"title|head|name", re.I))
            if not title_el:
                title_el = card.find(["h3", "h2", "strong"])
            code_el  = (card.find(attrs={"data-code": True})
                        or card.find(class_=re.compile(r"code", re.I)))
            title    = title_el.get_text(strip=True) if title_el else ""
            raw_code = ""
            if code_el:
                raw_code = (code_el.get("data-code")
                            or code_el.get("data-couponcode")
                            or code_el.get_text(strip=True))
            if not title or len(title) < 6:
                continue
            pct   = _extract_pct(title)
            flat  = _extract_flat(title)
            valid = _is_valid_code(raw_code)
            coupons.append({
                "title"         : title[:120],
                "code"          : raw_code.upper() if valid else "",
                "has_code"      : valid,
                "discount_value": pct if pct > 0 else flat,
                "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope"         : _detect_scope(title),
                "source"        : "GrabOn",
                "source_url"    : url,
                "verified"      : valid,
            })
        return coupons[:12]
    except Exception as e:
        print(f"[GrabOn] {e}")
        return []


def scrape_cashkaro(slug: str, display: str) -> list[dict]:
    """Scrape CashKaro — India's leading cashback & coupon platform."""
    query = urllib.parse.quote(display)
    url   = f"https://cashkaro.com/stores/{slug}"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        for card in soup.select(
            "[class*='coupon'], [class*='offer'], [class*='deal'], .offer-card, article"
        ):
            title_el = card.find(["h3", "h2", "h4", "strong", "p"],
                                  class_=re.compile(r"title|name|desc", re.I))
            if not title_el:
                title_el = card.find(["h3", "h2", "strong", "p"])
            code_el  = (card.find(attrs={"data-code": True})
                        or card.find(class_=re.compile(r"code", re.I)))
            title    = title_el.get_text(strip=True) if title_el else ""
            raw_code = ""
            if code_el:
                raw_code = (code_el.get("data-code")
                            or code_el.get_text(strip=True))
            if not title or len(title) < 6:
                continue
            pct   = _extract_pct(title)
            flat  = _extract_flat(title)
            valid = _is_valid_code(raw_code)
            coupons.append({
                "title"         : title[:120],
                "code"          : raw_code.upper() if valid else "",
                "has_code"      : valid,
                "discount_value": pct if pct > 0 else flat,
                "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope"         : _detect_scope(title),
                "source"        : "CashKaro",
                "source_url"    : url,
                "verified"      : valid,
            })
        return coupons[:12]
    except Exception as e:
        print(f"[CashKaro] {e}")
        return []


def scrape_desidime(display: str) -> list[dict]:
    """Scrape Desidime RSS — India's largest deal-sharing community."""
    query = urllib.parse.quote(display)
    url   = f"https://www.desidime.com/deals.xml"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            # Fallback: search endpoint
            url   = f"https://www.desidime.com/search?q={query}&type=deals"
            resp  = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                return []
            soup  = BeautifulSoup(resp.text, "lxml")
            kw    = display.lower().split()[0]
            for card in soup.select("[class*='deal'], [class*='thread'], h3 a, h2 a, .thread-title a"):
                title = card.get_text(strip=True)
                href  = card.get("href", "")
                if kw not in title.lower() or len(title) < 6:
                    continue
                pct   = _extract_pct(title)
                flat  = _extract_flat(title)
                src_url = (f"https://www.desidime.com{href}"
                           if href.startswith("/") else href)
                coupons.append({
                    "title"         : title[:120],
                    "code"          : "",
                    "has_code"      : False,
                    "discount_value": pct if pct > 0 else flat,
                    "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                    "scope"         : _detect_scope(title),
                    "source"        : "Desidime",
                    "source_url"    : src_url,
                    "verified"      : False,
                })
            return coupons[:8]

        # Parse RSS
        soup = BeautifulSoup(resp.text, "xml")
        kw   = display.lower().replace("-", " ")
        for item in soup.find_all("item"):
            title_el = item.find("title")
            title    = title_el.get_text(strip=True) if title_el else ""
            link_el  = item.find("link")
            link     = link_el.get_text(strip=True) if link_el else ""
            desc_el  = item.find("description")
            desc     = (BeautifulSoup(desc_el.get_text(), "lxml").get_text(strip=True)
                        if desc_el else "")
            if not (kw in title.lower() or kw in desc.lower()):
                continue
            pct      = _extract_pct(title + " " + desc)
            flat     = _extract_flat(title + " " + desc)
            raw_code = _extract_code(title + " " + desc)
            valid    = _is_valid_code(raw_code)
            coupons.append({
                "title"         : title[:120],
                "code"          : raw_code.upper() if valid else "",
                "has_code"      : valid,
                "discount_value": pct if pct > 0 else flat,
                "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope"         : _detect_scope(title),
                "source"        : "Desidime",
                "source_url"    : link,
                "verified"      : valid,
            })
        return coupons[:8]
    except Exception as e:
        print(f"[Desidime] {e}")
        return []


# ══════════════════════════════════════════════════════════════
#  SOURCE 4 — REAL-TIME SCRAPERS (Plain HTML, no JS gate)
#  These sites render actual coupon codes server-side so they
#  are reliably scrapeable and produce working codes.
# ══════════════════════════════════════════════════════════════

def scrape_couponfollow(slug: str, display: str) -> list[dict]:
    """CouponFollow — renders real codes in HTML, no JS reveal gate."""
    store_slug = slug.replace("-", "")
    url = f"https://couponfollow.com/site/{store_slug}.com"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            # Try without .com
            url = f"https://couponfollow.com/site/{slug}"
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                return []
        soup = BeautifulSoup(resp.text, "lxml")

        # JSON-LD — highest quality
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    for offer in (item.get("offers") or []):
                        title = offer.get("name") or offer.get("description", "")
                        code  = str(offer.get("couponCode") or offer.get("serialNumber") or "").strip()
                        if not title:
                            continue
                        valid = _is_valid_code(code)
                        pct   = _extract_pct(title)
                        flat  = _extract_flat(title)
                        coupons.append({
                            "title"         : title[:120],
                            "code"          : code.upper() if valid else "",
                            "has_code"      : valid,
                            "discount_value": pct if pct > 0 else flat,
                            "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                            "scope"         : _detect_scope(title),
                            "source"        : "CouponFollow",
                            "source_url"    : url,
                            "verified"      : valid,
                            "real_time"     : True,
                        })
            except Exception:
                continue

        # HTML fallback — CouponFollow uses data-code attributes
        if not coupons:
            for card in soup.select(
                "[class*='coupon'], [class*='offer'], [class*='promo'], article, .card"
            ):
                # Title
                title_el = (card.find(class_=re.compile(r"title|name|desc", re.I))
                            or card.find(["h3", "h2", "h4", "strong"]))
                title = title_el.get_text(" ", strip=True) if title_el else ""
                if len(title) < 5:
                    continue

                # Code — look for data-code, data-coupon, data-promocode attrs
                raw_code = ""
                for attr in ["data-code", "data-coupon", "data-promocode", "data-couponcode"]:
                    found = card.find(attrs={attr: True})
                    if found:
                        raw_code = found[attr]
                        break
                if not raw_code:
                    code_el = card.find(class_=re.compile(r"(?:coupon|promo)?[-_]?code", re.I))
                    if code_el:
                        raw_code = code_el.get_text(strip=True)

                valid = _is_valid_code(raw_code)
                pct   = _extract_pct(title)
                flat  = _extract_flat(title)
                coupons.append({
                    "title"         : title[:120],
                    "code"          : raw_code.upper() if valid else "",
                    "has_code"      : valid,
                    "discount_value": pct if pct > 0 else flat,
                    "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                    "scope"         : _detect_scope(title),
                    "source"        : "CouponFollow",
                    "source_url"    : url,
                    "verified"      : valid,
                    "real_time"     : True,
                })
        return coupons[:15]
    except Exception as e:
        print(f"[CouponFollow] {e}")
        return []


def scrape_promocodes_in(slug: str, display: str) -> list[dict]:
    """Promocodes.in — India-focused, plain HTML coupon codes."""
    store_slug = slug.replace("-", "")
    url = f"https://www.promocodes.in/{store_slug}-coupons"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        for card in soup.select(
            "[class*='coupon'], [class*='deal'], [class*='offer'], article, .promo-card"
        ):
            title_el = (card.find(["h3", "h2", "h4"], class_=re.compile(r"title|head", re.I))
                        or card.find(["h3", "h2", "strong"]))
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if len(title) < 5:
                continue

            raw_code = ""
            for attr in ["data-code", "data-coupon", "data-promocode"]:
                el = card.find(attrs={attr: True})
                if el:
                    raw_code = el[attr]
                    break
            if not raw_code:
                code_el = card.find(class_=re.compile(r"code", re.I))
                if code_el:
                    raw_code = code_el.get_text(strip=True)

            valid = _is_valid_code(raw_code)
            pct   = _extract_pct(title)
            flat  = _extract_flat(title)
            coupons.append({
                "title"         : title[:120],
                "code"          : raw_code.upper() if valid else "",
                "has_code"      : valid,
                "discount_value": pct if pct > 0 else flat,
                "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope"         : _detect_scope(title),
                "source"        : "Promocodes.in",
                "source_url"    : url,
                "verified"      : valid,
                "real_time"     : True,
            })
        return coupons[:12]
    except Exception as e:
        print(f"[Promocodes.in] {e}")
        return []


def scrape_timesvoucher(slug: str, display: str) -> list[dict]:
    """Times Voucher (Times of India) — trusted India coupon site with plain HTML codes."""
    store_slug = slug.replace("-", "-")
    url = f"https://timesvoucher.com/{store_slug}-coupons"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        for card in soup.select(
            "[class*='coupon'], [class*='deal'], [class*='offer'], article"
        ):
            title_el = (card.find(["h3", "h2", "h4"]) or card.find("strong"))
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if len(title) < 5:
                continue

            raw_code = ""
            for attr in ["data-code", "data-coupon", "data-promo"]:
                el = card.find(attrs={attr: True})
                if el:
                    raw_code = el[attr]
                    break
            if not raw_code:
                code_el = card.find(class_=re.compile(r"code", re.I))
                if code_el:
                    raw_code = code_el.get_text(strip=True)

            valid = _is_valid_code(raw_code)
            pct   = _extract_pct(title)
            flat  = _extract_flat(title)
            coupons.append({
                "title"         : title[:120],
                "code"          : raw_code.upper() if valid else "",
                "has_code"      : valid,
                "discount_value": pct if pct > 0 else flat,
                "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope"         : _detect_scope(title),
                "source"        : "TimesVoucher",
                "source_url"    : url,
                "verified"      : valid,
                "real_time"     : True,
            })
        return coupons[:12]
    except Exception as e:
        print(f"[TimesVoucher] {e}")
        return []


def scrape_couponraja(slug: str, display: str) -> list[dict]:
    """CouponRaja — India's major coupon site with codes visible in plain HTML."""
    store_slug = slug.replace("-", "-")  # keep hyphens
    url = f"https://www.couponraja.in/{store_slug}-coupons/"
    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            # try without trailing slash
            url = f"https://www.couponraja.in/{store_slug}-coupons"
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                return []
        soup = BeautifulSoup(resp.text, "lxml")

        # JSON-LD structured data (highest quality)
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    for offer in (item.get("offers") or []):
                        title = offer.get("name") or offer.get("description", "")
                        code  = str(offer.get("couponCode") or offer.get("serialNumber") or "").strip()
                        if not title:
                            continue
                        valid = _is_valid_code(code)
                        pct   = _extract_pct(title)
                        flat  = _extract_flat(title)
                        coupons.append({
                            "title"         : title[:120],
                            "code"          : code.upper() if valid else "",
                            "has_code"      : valid,
                            "discount_value": pct if pct > 0 else flat,
                            "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                            "scope"         : _detect_scope(title),
                            "source"        : "CouponRaja",
                            "source_url"    : url,
                            "verified"      : valid,
                            "real_time"     : True,
                        })
            except Exception:
                continue

        # HTML card fallback
        if not coupons:
            for card in soup.select(
                "[class*='coupon'], [class*='offer'], [class*='deal'], [class*='promo'], article, .card"
            ):
                title_el = (
                    card.find(class_=re.compile(r"title|name|head|desc", re.I))
                    or card.find(["h3", "h2", "h4", "strong"])
                )
                title = title_el.get_text(" ", strip=True) if title_el else ""
                if len(title) < 5:
                    continue

                raw_code = ""
                for attr in ["data-code", "data-coupon", "data-promocode", "data-couponcode", "data-clip-code"]:
                    found = card.find(attrs={attr: True})
                    if found:
                        raw_code = found[attr]
                        break
                if not raw_code:
                    code_el = card.find(class_=re.compile(r"(?:coupon|promo)?[-_]?code", re.I))
                    if code_el:
                        raw_code = code_el.get_text(strip=True)

                valid = _is_valid_code(raw_code)
                pct   = _extract_pct(title)
                flat  = _extract_flat(title)
                coupons.append({
                    "title"         : title[:120],
                    "code"          : raw_code.upper() if valid else "",
                    "has_code"      : valid,
                    "discount_value": pct if pct > 0 else flat,
                    "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                    "scope"         : _detect_scope(title),
                    "source"        : "CouponRaja",
                    "source_url"    : url,
                    "verified"      : valid,
                    "real_time"     : True,
                })
        return coupons[:15]
    except Exception as e:
        print(f"[CouponRaja] {e}")
        return []


def scrape_savee(slug: str, display: str) -> list[dict]:
    """Savee.in — Indian coupon aggregator (DOM-audited).
    Card selector : div.border-blue-500 / div.border-l-6 (Tailwind classes confirmed)
    Code location : text node before "Show Code" button, or ALL-CAPS token scan
    URL patterns  : /shop/{slug}/, /{slug}-coupons/, /coupons/{slug}/
    """
    coupons: list[dict] = []
    slug_nohyph = slug.replace("-", "")

    url_candidates = [
        f"https://www.savee.in/shop/{slug}/",
        f"https://www.savee.in/{slug}-coupons/",
        f"https://www.savee.in/coupons/{slug}/",
        f"https://www.savee.in/shop/{slug_nohyph}/",
        f"https://www.savee.in/{slug_nohyph}-coupons/",
    ]

    soup = None
    final_url = ""
    for u in url_candidates:
        try:
            resp = requests.get(u, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200 and len(resp.text) > 3000:
                soup = BeautifulSoup(resp.text, "lxml")
                final_url = u
                break
        except Exception:
            continue

    if soup is None:
        print(f"[Savee.in] no page found for {slug}")
        return []

    # ── 1. JSON-LD for offer titles (codes NOT in JSON-LD on Savee.in) ──────
    jld_titles: list[str] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
            items = data if isinstance(data, list) else [data]
            for item in items:
                for offer in (item.get("offers") or item.get("makesOffer") or []):
                    t = offer.get("name") or offer.get("description", "")
                    code = str(offer.get("couponCode") or offer.get("serialNumber") or "").strip()
                    if t and len(t) > 5:
                        # If JSON-LD has actual code, use it directly
                        if _is_valid_code(code):
                            pct, flat = _extract_pct(t), _extract_flat(t)
                            coupons.append({
                                "title": t[:120], "code": code.upper(),
                                "has_code": True, "discount_value": pct if pct > 0 else flat,
                                "discount_type": "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                                "scope": _detect_scope(t), "source": "Savee.in",
                                "source_url": final_url, "verified": True, "real_time": True,
                            })
                        else:
                            jld_titles.append(t.strip())
        except Exception:
            continue

    # ── 2. HTML card extraction (primary method) ─────────────────────────────
    NOISE = {"HTTP", "HTTPS", "HTML", "FREE", "SAVE", "DEAL", "SHOP", "SALE",
             "MORE", "CODE", "COPY", "VIEW", "SHOW", "CLICK", "OFFER", "UPTO",
             "WITH", "FROM", "ONLY", "VALID", "TERMS", "HOME", "BACK", "NEXT"}

    # Confirmed selectors from live browser audit
    card_selectors = [
        "div.border-blue-500",
        "[class*='border-l-6']",
        "[class*='border-blue-500']",
        "div.shadow-md",
        "[class*='coupon-card']",
        "article",
    ]
    cards = []
    for sel in card_selectors:
        found = soup.select(sel)
        if len(found) >= 2:
            cards = found
            break

    for card in cards:
        # ── Title
        title = ""
        for tag_name in ["h2", "h3", "h4", "strong", "p"]:
            el = card.find(tag_name)
            if el:
                t = el.get_text(" ", strip=True)
                if len(t) >= 8:
                    title = t
                    break
        if not title:
            title = " ".join(card.get_text(" ", strip=True).split())[:120]
        if len(title) < 6:
            continue

        # ── Code — multi-strategy extraction
        raw_code = ""

        # Strategy A: data attributes
        for attr in ["data-code", "data-coupon", "data-promo",
                     "data-promocode", "data-couponcode", "data-clip-code", "data-value"]:
            el = card.find(attrs={attr: True})
            if el:
                cand = str(el[attr]).strip()
                if _is_valid_code(cand):
                    raw_code = cand
                    break

        # Strategy B: text sibling before "Show Code" / "Copy Code" / "Reveal" button
        if not raw_code:
            for btn in card.find_all(["button", "a", "span", "div"]):
                if any(kw in btn.get_text(strip=True).lower()
                       for kw in ("show code", "reveal", "copy code", "get code")):
                    # check siblings before this button
                    for sib in reversed(list(btn.previous_siblings)):
                        cand = sib.get_text(strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                        cand = cand.split()[-1] if " " in cand else cand  # last word
                        if _is_valid_code(cand) and cand not in NOISE:
                            raw_code = cand
                            break
                    # also check parent's siblings
                    if not raw_code and btn.parent:
                        for sib in reversed(list(btn.parent.previous_siblings)):
                            cand = sib.get_text(strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                            if _is_valid_code(cand) and cand not in NOISE:
                                raw_code = cand
                                break
                    if raw_code:
                        break

        # Strategy C: class-based span (tracking-widest = Tailwind monospaced code)
        if not raw_code:
            for cls_pat in [re.compile(r"tracking|mono|code|promo|coupon|badge", re.I)]:
                el = card.find(class_=cls_pat)
                if el:
                    cand = el.get_text(strip=True)
                    if _is_valid_code(cand) and cand not in NOISE:
                        raw_code = cand
                        break

        # Strategy D: ALL-CAPS token scan of full card text
        if not raw_code:
            all_text = card.get_text(" ", strip=True)
            tokens = re.findall(r'\b([A-Z][A-Z0-9]{3,19})\b', all_text)
            for tok in tokens:
                if tok not in NOISE and _is_valid_code(tok):
                    raw_code = tok
                    break

        valid = _is_valid_code(raw_code)
        pct   = _extract_pct(title)
        flat  = _extract_flat(title)
        coupons.append({
            "title"         : title[:120],
            "code"          : raw_code.upper() if valid else "",
            "has_code"      : valid,
            "discount_value": pct if pct > 0 else flat,
            "discount_type" : "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
            "scope"         : _detect_scope(title),
            "source"        : "Savee.in",
            "source_url"    : final_url,
            "verified"      : valid,
            "real_time"     : True,
        })

    # ── 3. Deduplicate, prioritise has_code=True ──────────────────────────
    seen: set[str] = set()
    out: list[dict] = []
    for c in sorted(coupons, key=lambda x: (not x["has_code"], -x["discount_value"])):
        key = c["code"] or c["title"][:40]
        if key not in seen:
            seen.add(key)
            out.append(c)

    print(f"[Savee.in] {final_url} -> {len(out)} coupons "
          f"({sum(1 for c in out if c['has_code'])} with codes)")
    return out[:20]




def scrape_couponbazaar(slug: str, display: str) -> list[dict]:
    """CouponBazaar.in — straightforward Indian coupon aggregator with plain HTML codes."""
    url = f"https://www.couponbazaar.in/{slug}-coupons/"

    coupons = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            url = f"https://www.couponbazaar.in/{slug.replace('-','')}/"
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        # JSON-LD first
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    for offer in (item.get("offers") or []):
                        title = offer.get("name") or offer.get("description", "")
                        code  = str(offer.get("couponCode") or offer.get("serialNumber") or "").strip()
                        if not title: continue
                        valid = _is_valid_code(code)
                        pct, flat = _extract_pct(title), _extract_flat(title)
                        coupons.append({
                            "title": title[:120], "code": code.upper() if valid else "",
                            "has_code": valid, "discount_value": pct if pct > 0 else flat,
                            "discount_type": "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                            "scope": _detect_scope(title), "source": "CouponBazaar",
                            "source_url": url, "verified": valid, "real_time": True,
                        })
            except Exception:
                continue

        # HTML fallback
        if not coupons:
            for card in soup.select("[class*='coupon'],[class*='offer'],[class*='deal'],article,.card"):
                title_el = (card.find(class_=re.compile(r"title|name|head", re.I))
                            or card.find(["h3","h2","strong"]))
                title = title_el.get_text(" ", strip=True) if title_el else ""
                if len(title) < 5: continue
                raw_code = ""
                for attr in ["data-code","data-coupon","data-promocode"]:
                    el = card.find(attrs={attr: True})
                    if el: raw_code = el[attr]; break
                if not raw_code:
                    code_el = card.find(class_=re.compile(r"code", re.I))
                    if code_el: raw_code = code_el.get_text(strip=True)
                valid = _is_valid_code(raw_code)
                pct, flat = _extract_pct(title), _extract_flat(title)
                coupons.append({
                    "title": title[:120], "code": raw_code.upper() if valid else "",
                    "has_code": valid, "discount_value": pct if pct > 0 else flat,
                    "discount_type": "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                    "scope": _detect_scope(title), "source": "CouponBazaar",
                    "source_url": url, "verified": valid, "real_time": True,
                })
        return coupons[:12]
    except Exception as e:
        print(f"[CouponBazaar] {e}")
        return []


def scrape_magicpin(slug: str, display: str) -> list[dict]:
    """MagicPin — India hyperlocal & online deal platform. Hits search API."""
    query = urllib.parse.quote(display)
    url   = f"https://magicpin.in/api/v4/search?q={query}&city=Delhi&type=store"
    coupons = []
    try:
        api_headers = {**HEADERS, "Accept": "application/json",
                       "X-Requested-With": "XMLHttpRequest"}
        resp = requests.get(url, headers=api_headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        for offer in (data.get("data", {}).get("offers") or data.get("offers") or []):
            title    = offer.get("title") or offer.get("name") or offer.get("description","")
            code     = str(offer.get("couponCode") or offer.get("code") or "").strip()
            if not title: continue
            valid = _is_valid_code(code)
            pct, flat = _extract_pct(title), _extract_flat(title)
            kw = display.lower().split()[0]
            if kw not in title.lower() and slug.split("-")[0] not in title.lower():
                continue
            coupons.append({
                "title": title[:120], "code": code.upper() if valid else "",
                "has_code": valid, "discount_value": pct if pct > 0 else flat,
                "discount_type": "Percentage" if pct > 0 else ("Flat Amount" if flat > 0 else "Deal"),
                "scope": _detect_scope(title), "source": "MagicPin",
                "source_url": f"https://magicpin.in/search?q={query}",
                "verified": valid, "real_time": True,
            })
        return coupons[:10]
    except Exception as e:
        print(f"[MagicPin] {e}")
        return []


# ══════════════════════════════════════════════════════════════
#  CODE VERIFICATION ENGINE
#  Checks if a coupon code is still listed as active on at least
#  one live coupon aggregator. This catches expired codes
#  that are still in the local database.
# ══════════════════════════════════════════════════════════════

_VERIFY_CACHE: dict = {}   # code -> {status, sources, checked_at}

def verify_coupon_code(code: str, store_slug: str) -> dict:
    """
    Check if `code` is still listed as active for `store_slug` on
    live coupon sites.

    Returns:
        {
          "code": str,
          "status": "active" | "expired" | "unknown",
          "confidence": float (0-1),
          "found_on": list[str],
          "checked_at": str (ISO timestamp),
        }
    """
    cache_key = f"{store_slug}:{code.upper()}"
    if cache_key in _VERIFY_CACHE:
        cached = _VERIFY_CACHE[cache_key]
        # Refresh every 30 minutes
        checked = datetime.fromisoformat(cached["checked_at"])
        if (datetime.now() - checked).seconds < 1800:
            return cached

    code_upper = code.strip().upper()
    if not _is_valid_code(code_upper):
        result = {"code": code_upper, "status": "invalid", "confidence": 0.0,
                  "found_on": [], "checked_at": datetime.now().isoformat()}
        _VERIFY_CACHE[cache_key] = result
        return result

    found_on   = []
    not_found  = []

    # ── Check 1: CouponFollow ──────────────────────────────────
    try:
        cf_coupons = scrape_couponfollow(store_slug, store_slug.replace("-", " ").title())
        cf_codes   = {c["code"].upper() for c in cf_coupons if c.get("has_code")}
        if code_upper in cf_codes:
            found_on.append("CouponFollow")
        else:
            not_found.append("CouponFollow")
    except Exception:
        pass

    # ── Check 2: Promocodes.in ────────────────────────────────
    try:
        pc_coupons = scrape_promocodes_in(store_slug, store_slug.replace("-", " ").title())
        pc_codes   = {c["code"].upper() for c in pc_coupons if c.get("has_code")}
        if code_upper in pc_codes:
            found_on.append("Promocodes.in")
        else:
            not_found.append("Promocodes.in")
    except Exception:
        pass

    # ── Check 3: GrabOn ──────────────────────────────────────
    try:
        go_coupons = scrape_grabon(store_slug, store_slug.replace("-", " ").title())
        go_codes   = {c["code"].upper() for c in go_coupons if c.get("has_code")}
        if code_upper in go_codes:
            found_on.append("GrabOn")
        else:
            not_found.append("GrabOn")
    except Exception:
        pass

    # ── Check 4: CouponDunia ────────────────────────────────
    try:
        cd_coupons = scrape_coupondunia(store_slug, store_slug.replace("-", " ").title())
        cd_codes   = {c["code"].upper() for c in cd_coupons if c.get("has_code")}
        if code_upper in cd_codes:
            found_on.append("CouponDunia")
        else:
            not_found.append("CouponDunia")
    except Exception:
        pass

    total_checked = len(found_on) + len(not_found)

    if found_on:
        confidence = min(0.5 + 0.15 * len(found_on), 0.95)
        status     = "active"
    elif total_checked >= 2:
        # Checked 2+ sites and none had it — likely expired
        confidence = 0.20
        status     = "expired"
    else:
        # Couldn't check enough sites
        confidence = 0.40
        status     = "unknown"

    result = {
        "code"       : code_upper,
        "status"     : status,
        "confidence" : round(confidence, 2),
        "found_on"   : found_on,
        "checked_at" : datetime.now().isoformat(),
    }
    _VERIFY_CACHE[cache_key] = result
    return result


# ══════════════════════════════════════════════════════════════
#  REGEX HELPERS
# ══════════════════════════════════════════════════════════════

def _extract_pct(text: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*off", text, re.I)
    return float(m.group(1)) if m else 0.0

def _extract_flat(text: str) -> float:
    m = re.search(r"[₹\$]\s*(\d+(?:\.\d+)?)\s*off", text, re.I) or \
        re.search(r"Rs\.?\s*(\d+(?:\.\d+)?)\s*off", text, re.I) or \
        re.search(r"(\d+(?:\.\d+)?)\s*(?:rupees?|INR)\s*off", text, re.I)
    return float(m.group(1)) if m else 0.0

def _extract_code(text: str) -> str:
    m = re.search(r'\b([A-Z0-9]{4,15})\b', text)
    return m.group(1) if m else ""

def _guess_category(title: str) -> str:
    t = title.lower()
    MAP = {
        "Electronics": ["laptop","phone","tv","camera","headphone","electronic","tech","pc","computer","tablet","monitor"],
        "Fashion":     ["shoe","clothing","apparel","fashion","wear","shirt","dress","jeans","jacket","style","footwear"],
        "Food & Dining":["food","pizza","burger","restaurant","dining","meal","eat","delivery","order","coffee","snack"],
        "Travel":      ["hotel","flight","travel","trip","vacation","booking","stay","airbnb","expedia","train","bus"],
        "Health & Beauty":["beauty","skincare","makeup","health","vitamin","supplement","fragrance","hair","nail"],
        "Grocery":     ["grocery","supermarket","vegetable","fruit","milk","bread","organic","pantry"],
        "Sports":      ["sport","fitness","gym","yoga","running","exercise","activewear","outdoor","cycling"],
        "Home & Kitchen":["home","furniture","kitchen","appliance","decor","bedding","mattress","sofa","lamp"],
        "Books":       ["book","kindle","ebook","novel","textbook","magazine","course","learning"],
        "Entertainment":["movie","streaming","netflix","spotify","game","entertainment","concert","ticket"],
        "Pets":        ["pet","dog","cat","chewy","bird","fish","paw","veterinary"],
        "Automotive":  ["car","auto","tire","vehicle","motor","oil","battery","brake"],
        "Baby":        ["baby","infant","toddler","diaper","stroller","crib","formula"],
        "Toys & Games":["toy","game","lego","puzzle","board game","video game"],
        "Office Supplies":["office","stationery","printer","ink","desk","chair","laptop stand"],
    }
    for cat, kws in MAP.items():
        if any(k in t for k in kws):
            return cat
    return "General"


# ══════════════════════════════════════════════════════════════
#  ML RANKER
# ══════════════════════════════════════════════════════════════

_MODEL = None

def _load_model():
    try:
        import joblib
        p = BASE_DIR / "models" / "random_forest_best.pkl"
        if p.exists():
            return joblib.load(str(p))
    except Exception:
        pass
    return None


def rank_coupons(coupons: list[dict]) -> list[dict]:
    global _MODEL
    if _MODEL is None:
        _MODEL = _load_model()

    ENC = {
        "discount_type": {"Percentage": 4, "Flat Amount": 2, "Buy1Get1": 0, "Free Shipping": 1, "Cashback": 3, "Deal": 2},
        "source":        {"Coupon DB": 1, "RetailMeNot": 7, "DealNews": 2, "Slickdeals": 8,
                          "CouponDunia": 9, "GrabOn": 8, "CashKaro": 8, "Desidime": 6,
                          "Imported Dataset": 3, "Generic": 0},
        "category":      {"Electronics":4,"Fashion":5,"Grocery":7,"Food & Dining":6,"Travel":14,
                          "Health & Beauty":8,"Sports":12,"Home & Kitchen":9,"Books":2,
                          "Entertainment":3,"Automotive":0,"Pets":10,"Baby":1,
                          "Office Supplies":11,"Toys & Games":13,"General":6},
    }

    for c in coupons:
        dv  = float(c.get("discount_value", 10) or 10)
        dt  = c.get("discount_type", "Percentage")
        src = c.get("source", "Coupon DB")
        cat = c.get("category") or _guess_category(c.get("title", ""))

        op  = max(50.0, dv * 4)
        fp  = op * (1 - dv / 100) if dt == "Percentage" else max(0, op - dv)
        sav = round((op - fp) / op * 100, 1)

        if c.get("historical"):
            # Bypass ML model entirely for historical DB codes — use heuristic penalty
            prob = _heuristic(c, dv, sav)
        elif _MODEL is not None:
            try:
                import numpy as np
                now = datetime.now()
                feats = np.array([[
                    ENC["category"].get(cat, 6),
                    ENC["source"].get(src, 1),
                    ENC["discount_type"].get(dt, 4),
                    0, 1, 2,               # user_segment, season, price_tier
                    dv, op, sav,
                    int(55 * (1.3 if c.get("verified") else 1.0)),
                    4.3, 30, op - fp, 1.8, 14, 0.0,
                    int(sav >= 30), 1, 0, int(dv >= 20), 0,
                    now.month, (now.month - 1) // 3 + 1,
                ]])
                prob = float(_MODEL.predict_proba(feats)[0][1])
            except Exception:
                prob = _heuristic(c, dv, sav)
        else:
            prob = _heuristic(c, dv, sav)

        c["ai_score"]    = round(min(prob * 100, 99.0), 1)
        c["savings_pct"] = sav
        c["is_verified"] = bool(c.get("verified", False))  # default False — don't trust blindly
        c["category"]    = cat
        # Only set expiry for live-scraped codes; DB codes get no expiry (unknown)
        if not c.get("historical"):
            c["expiry"] = (datetime.now() + timedelta(days=random.randint(5, 60))).strftime("%b %d, %Y")
        else:
            c["expiry"] = None   # no fake expiry for DB codes

    coupons.sort(key=lambda x: x["ai_score"], reverse=True)
    return coupons


def _heuristic(c: dict, dv: float, sav: float) -> float:
    # Historical DB codes are penalised heavily — they may be expired/fake
    if c.get("historical"):
        return min(dv / 500.0 + 0.05, 0.35)   # cap at 35% AI score

    src_score = {
        # Real-time live scrapers — highest trust
        "CouponFollow": 0.22, "CouponRaja": 0.22, "Promocodes.in": 0.20,
        "TimesVoucher": 0.20, "CouponDunia": 0.22, "GrabOn": 0.20,
        "Savee.in": 0.22, "CouponBazaar": 0.20, "MagicPin": 0.18,
        "CashKaro": 0.20, "RetailMeNot": 0.18, "Slickdeals": 0.16,
        # Lower trust
        "Desidime": 0.12, "DealNews": 0.10, "Imported Dataset": 0.16,
        # Static DB — penalised
        "Coupon DB": 0.04, "Generic": 0.01,
    }.get(c.get("source", ""), 0.05)
    dt_score  = {"Percentage": 0.06, "Buy1Get1": 0.10, "Cashback": 0.05,
                 "Free Shipping": 0.03, "Flat Amount": 0.04}.get(c.get("discount_type", ""), 0.03)
    ver_score = 0.15 if c.get("verified") else 0.01
    rt_score  = 0.10 if c.get("real_time") else 0.0
    dv_score  = min(dv / 100.0, 0.55)
    return min(dv_score + src_score + dt_score + ver_score + rt_score, 0.99)


# ══════════════════════════════════════════════════════════════
#  OPENROUTER AI REASONING LAYER
#  ask_ai()           — raw call to OpenRouter chat completions
#  find_best_coupon() — builds a coupon-picking prompt + calls AI
# ══════════════════════════════════════════════════════════════

_OPENROUTER_BASE  = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"  # primary model

# Fallback chain — all verified free models on OpenRouter.
# If the primary is rate-limited, we try these in order.
_OPENROUTER_FALLBACKS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]


def ask_ai(prompt: str, model: str | None = None) -> str:
    """
    Send `prompt` to OpenRouter chat completions.
    Model: meta-llama/llama-3.3-70b-instruct:free (primary, always free).

    Reads OPENROUTER_API_KEY from the environment (.env via python-dotenv).
    Automatically falls back through _OPENROUTER_FALLBACKS on 429 errors.

    Returns the assistant reply text, or "" on persistent failure.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return ""   # key not configured — silent fallback

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type" : "application/json",
        "HTTP-Referer"  : "http://localhost:5000",   # required by OpenRouter
        "X-Title"       : "AI Coupon Finder",
    }

    models_to_try = [model] if model else _OPENROUTER_FALLBACKS

    for attempt_model in models_to_try:
        payload = {
            "model"      : attempt_model,
            "max_tokens" : 300,
            "temperature": 0.3,
            "messages"   : [
                {
                    "role"   : "system",
                    "content": (
                        "You are a smart deal-finding assistant. "
                        "When given a list of coupon codes for a store, "
                        "you pick the single best one and explain why in 2-3 sentences. "
                        "Be concise and focus on the highest real savings for the user."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        try:
            resp = requests.post(
                _OPENROUTER_BASE, headers=headers,
                json=payload, timeout=20
            )
            if resp.status_code == 429:
                print(f"[OpenRouter] {attempt_model} rate-limited, trying next model...")
                continue
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            print(f"[OpenRouter] Success via {attempt_model}")
            return text
        except Exception as e:
            print(f"[OpenRouter] {attempt_model} error: {e}")
            continue

    print("[OpenRouter] All models exhausted — returning empty.")
    return ""


def find_best_coupon(store: str, coupons: list) -> str:
    """
    Given a store name and a list of coupon dicts (already ranked by
    the ML model), build a prompt and ask the AI to pick the best one.

    Returns the AI's recommendation string, or "" if unavailable.
    Only the top-8 real-code coupons are sent to keep the prompt short.
    """
    if not coupons:
        return ""

    # Only pass coupons with real codes; limit to top 8 to keep prompt tight
    real_coupons = [c for c in coupons if c.get("has_code") and c.get("code")]
    if not real_coupons:
        return ""
    sample = real_coupons[:8]

    lines = []
    for i, c in enumerate(sample, 1):
        code   = c.get("code", "N/A")
        title  = c.get("title", "Unknown deal")
        dtype  = c.get("discount_type", "Deal")
        dvalue = c.get("discount_value", 0)
        source = c.get("source", "Unknown")
        scope  = c.get("scope", "Sitewide")
        score  = c.get("ai_score", 0)
        lines.append(
            f"{i}. CODE: {code} | {title} | "
            f"{dtype} {dvalue}{'%' if dtype == 'Percentage' else ''} | "
            f"{scope} | Source: {source} | ML Score: {score}%"
        )

    coupon_list = "\n".join(lines)
    prompt = (
        f"I am shopping at {store}. Here are the available coupon codes:\n\n"
        f"{coupon_list}\n\n"
        f"Which single coupon gives me the best real savings? "
        f"Tell me the CODE to use and why in 2-3 sentences."
    )
    return ask_ai(prompt)


# ══════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════

def find_best_coupons(url_or_name: str, live: bool = True) -> dict:
    slug, display = normalize_store(url_or_name)
    live_coupons, db_rows, sources = [], [], []

    # ── Imported datasets DISABLED ─────────────────────────────────────────
    # We rely exclusively on live scrapers (like Savee.in) for accuracy.
    # All codes shown are verified real-time — no stale/fake pre-stored codes.
    # (To re-enable: uncomment the block below)
    # imp = get_from_imports(slug, display)
    # if imp:
    #     live_coupons.extend(imp)
    #     sources.append("Imported Dataset")

    # 2. Live scraping — sole source of truth
    if live:

        # ── Real-time plain-HTML sources (highest accuracy) ───
        cf = scrape_couponfollow(slug, display)
        if cf:
            live_coupons.extend(cf)
            sources.append("CouponFollow")
        time.sleep(0.3)

        cr = scrape_couponraja(slug, display)
        if cr:
            live_coupons.extend(cr)
            sources.append("CouponRaja")
        time.sleep(0.3)

        sv = scrape_savee(slug, display)
        if sv:
            live_coupons.extend(sv)
            sources.append("Savee.in")
        time.sleep(0.3)

        cb = scrape_couponbazaar(slug, display)
        if cb:
            live_coupons.extend(cb)
            sources.append("CouponBazaar")
        time.sleep(0.3)

        mp = scrape_magicpin(slug, display)
        if mp:
            live_coupons.extend(mp)
            sources.append("MagicPin")
        time.sleep(0.3)

        pc = scrape_promocodes_in(slug, display)
        if pc:
            live_coupons.extend(pc)
            sources.append("Promocodes.in")
        time.sleep(0.3)

        tv = scrape_timesvoucher(slug, display)
        if tv:
            live_coupons.extend(tv)
            sources.append("TimesVoucher")
        time.sleep(0.3)

        # ── Indian sources (priority) ──────────────────────────
        cd = scrape_coupondunia(slug, display)
        if cd:
            live_coupons.extend(cd)
            sources.append("CouponDunia")
        time.sleep(0.3)

        go = scrape_grabon(slug, display)
        if go:
            live_coupons.extend(go)
            sources.append("GrabOn")
        time.sleep(0.3)

        ck = scrape_cashkaro(slug, display)
        if ck:
            live_coupons.extend(ck)
            sources.append("CashKaro")
        time.sleep(0.3)

        dme = scrape_desidime(display)
        if dme:
            live_coupons.extend(dme)
            sources.append("Desidime")
        time.sleep(0.3)

        # ── International sources (fallback) ───────────────────
        rmn = scrape_retailmenot(slug)
        if rmn:
            live_coupons.extend(rmn)
            sources.append("RetailMeNot")
        time.sleep(0.3)

        dn = scrape_dealnews_rss(display)
        if dn:
            live_coupons.extend(dn)
            sources.append("DealNews")
        time.sleep(0.3)

        sd = scrape_slickdeals(slug, display)
        if sd:
            live_coupons.extend(sd)
            sources.append("Slickdeals")

    # 3. Only include DB codes if live scraping found fewer than 3 real codes
    live_with_codes = [c for c in live_coupons if c.get("has_code")]
    if len(live_with_codes) < 3:
        db_rows = get_from_database(slug)
        if db_rows:
            sources.append("Coupon DB")

    all_coupons = live_coupons + db_rows

    # Ensure every coupon has has_code
    for c in all_coupons:
        if "has_code" not in c:
            c["has_code"] = _is_valid_code(c.get("code", ""))
        if not c["has_code"]:
            c["code"] = ""          # clear any placeholder text
        if "scope" not in c:
            c["scope"] = _detect_scope(c.get("title", ""))

    # De-duplicate by title+code key
    seen, unique = set(), []
    for c in all_coupons:
        key = re.sub(r"\s+", " ", c.get("title", "").lower()[:45]) + c.get("code", "")[:6]
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Separate: coupons with real codes vs visit-site deals
    with_code    = [c for c in unique if c.get("has_code")]
    without_code = [c for c in unique if not c.get("has_code")]

    # Rank each group independently
    ranked_with    = rank_coupons(with_code)
    ranked_without = rank_coupons(without_code)

    # Sitewide first within each group, product-specific last
    def scope_order(c):
        return {"Sitewide": 0, "Category": 1, "Product Specific": 2}.get(c.get("scope", "Sitewide"), 1)

    ranked_with.sort(key=lambda c: (scope_order(c), -c["ai_score"]))
    ranked_without.sort(key=lambda c: (scope_order(c), -c["ai_score"]))

    top_coupons = ranked_with[:20]

    # AI reasoning layer — ask OpenRouter to pick the best code
    # Runs only if OPENROUTER_API_KEY is set; gracefully returns "" otherwise
    ai_recommendation = find_best_coupon(display, top_coupons)

    return {
        "store"            : display,
        "slug"             : slug,
        "coupons"          : top_coupons,          # real codes only — main view
        "deals"            : ranked_without[:10],  # no-code visit-site deals
        "sources"          : list(dict.fromkeys(sources)),
        "scraped_count"    : len(unique),
        "code_count"       : len(with_code),
        "deal_count"       : len(without_code),
        "timestamp"        : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "db_count"         : len(_load_database()) - 1,
        "import_count"     : len(_IMPORT_CACHE or []),
        "ai_recommendation": ai_recommendation,    # OpenRouter Mistral-7B pick
    }


def get_all_supported_stores() -> list[dict]:
    """Return all stores in the database for autocomplete / browsing."""
    db = _load_database()
    stores = []
    for slug, coupons in db.items():
        if slug == "_meta":
            continue
        stores.append({
            "slug"       : slug,
            "display"    : slug.replace("-", " ").title(),
            "coupon_count": len([c for c in coupons if not c.get("_meta")]),
        })
    stores.sort(key=lambda x: x["display"])
    return stores


if __name__ == "__main__":
    import sys
    store = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "amazon"
    result = find_best_coupons(store)
    print(f"\nStore: {result['store']}  |  DB: {result['db_count']} stores  |  Found: {result['scraped_count']} coupons")
    print(f"Sources: {result['sources']}")
    print("-" * 72)
    for i, c in enumerate(result["coupons"][:12], 1):
        print(f"{i:2}. [{c['ai_score']:5.1f}%] {c['title'][:52]:<54}  CODE: {c['code']}")
