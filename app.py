"""
=============================================================
  AI COUPON FINDER — FLASK APP v4
  Endpoints:
    GET  /                      → main UI
    POST /api/find-coupons      → search + AI recommendation (OpenRouter)
    GET  /api/stores            → list all supported stores
    GET  /api/imports           → list imported datasets
    POST /api/import-url        → import dataset from any URL
    POST /api/upload            → upload CSV/JSON file
    DELETE /api/import/<name>   → delete an imported dataset
    POST /api/reload-db         → force reload coupon_database.json
    POST /api/ask-ai            → raw OpenRouter prompt endpoint
=============================================================
"""

import os, json
from flask import Flask, render_template, request, jsonify
from scraper_engine import (
    find_best_coupons, get_all_supported_stores,
    list_imports, import_from_url, import_from_upload,
    delete_import, reload_imports, _load_database,
    verify_coupon_code, ask_ai, find_best_coupon
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


# ─── MAIN PAGE ───────────────────────────────────────────────

@app.route("/")
def index():
    from flask import make_response
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ─── COUPON SEARCH ───────────────────────────────────────────

@app.route("/api/find-coupons", methods=["POST"])
def api_find_coupons():
    data = request.get_json(force=True)
    q    = (data.get("query") or "").strip()
    if not q:
        return jsonify({"error": "Please enter a website URL or store name"}), 400
    # find_best_coupons() already calls find_best_coupon() + ask_ai() internally.
    # The result dict includes 'ai_recommendation' when OPENROUTER_API_KEY is set.
    result = find_best_coupons(q, live=True)
    return jsonify(result)


# ─── RAW AI PROMPT (for testing / direct queries) ─────────────────

@app.route("/api/ask-ai", methods=["POST"])
def api_ask_ai():
    """
    Direct access to the OpenRouter AI layer.
    Body: { "prompt": "Which coupon is best?" }
    Returns: { "response": "...", "model": "...", "has_key": bool }
    """
    data   = request.get_json(force=True)
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    import os
    has_key  = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    response = ask_ai(prompt)
    return jsonify({
        "response": response,
        "model"   : "mistralai/mistral-7b-instruct:free",
        "has_key" : has_key,
    })


# ─── AI CHATBOT ───────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Conversational AI endpoint for the chatbot widget.
    Body: { "message": str, "context": { "store": str, "coupons": list } }
    Returns: { "reply": str, "has_key": bool }
    """
    import os
    data    = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    ctx     = data.get("context") or {}
    if not message:
        return jsonify({"error": "message is required"}), 400

    store   = ctx.get("store", "")
    coupons = ctx.get("coupons") or []

    # Build a context-aware system prompt
    system = (
        "You are DealSense AI, a friendly and knowledgeable coupon assistant. "
        "You help users save money by giving concise, practical advice about deals, "
        "coupon codes, and shopping strategies. "
        "Be conversational, helpful and keep answers under 3 sentences. "
        "If asked about a specific store's coupons you already have context about, use it. "
        "Never make up coupon codes."
    )
    if store and coupons:
        top = coupons[:5]
        lines = [f"- CODE: {c.get('code','N/A')} | {c.get('title','')[:60]} | {c.get('discount_type','')} {c.get('discount_value','')}{'%' if c.get('discount_type')=='Percentage' else ''}" for c in top]
        ctx_block = f"\n\nCurrent store: {store}\nTop coupons available:\n" + "\n".join(lines)
        system += ctx_block

    full_prompt = f"[System]\n{system}\n\n[User]\n{message}"
    reply = ask_ai(full_prompt)
    if not reply:
        reply = "I'm having trouble connecting right now. Please try again in a moment!"

    has_key = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    return jsonify({"reply": reply, "has_key": has_key})




@app.route("/api/quick-search")
def quick_search():
    q = (request.args.get("q") or "amazon").strip()
    result = find_best_coupons(q, live=False)
    return jsonify(result)


# ─── CODE VERIFICATION ─────────────────────────────────────

@app.route("/api/verify-code", methods=["POST"])
def api_verify_code():
    """
    Real-time check whether a coupon code is still active.
    Body: { "code": "SAVE20", "store": "amazon" }
    Returns: { code, status, confidence, found_on, checked_at }
    """
    data  = request.get_json(force=True)
    code  = (data.get("code") or "").strip()
    store = (data.get("store") or "").strip()
    if not code:
        return jsonify({"error": "code is required"}), 400
    if not store:
        return jsonify({"error": "store is required"}), 400
    result = verify_coupon_code(code, store)
    return jsonify(result)


# ─── STORE BROWSER ───────────────────────────────────────────

@app.route("/api/stores")
def api_stores():
    return jsonify(get_all_supported_stores())


# ─── DATASET MANAGEMENT ──────────────────────────────────────

@app.route("/api/imports")
def api_list_imports():
    return jsonify({"imports": list_imports()})


@app.route("/api/import-url", methods=["POST"])
def api_import_url():
    data = request.get_json(force=True)
    url  = (data.get("url") or "").strip()
    name = (data.get("filename") or "").strip() or None
    if not url:
        return jsonify({"status": "error", "message": "URL is required"}), 400
    result = import_from_url(url, name)
    return jsonify(result), (200 if result["status"] == "ok" else 400)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    f   = request.files["file"]
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in [".csv", ".json"]:
        return jsonify({"status": "error", "message": "Only .csv or .json files allowed"}), 400
    result = import_from_upload(f.read(), f.filename)
    return jsonify(result), (200 if result["status"] == "ok" else 400)


@app.route("/api/import/<filename>", methods=["DELETE"])
def api_delete_import(filename):
    result = delete_import(filename)
    return jsonify(result), (200 if result["status"] == "ok" else 400)


@app.route("/api/reload-db", methods=["POST"])
def api_reload_db():
    global _load_database
    import scraper_engine as se
    se._DB_CACHE    = None
    se._IMPORT_CACHE = None
    se._load_database()
    se.reload_imports()
    return jsonify({
        "status"       : "ok",
        "db_stores"    : len(se._DB_CACHE) - 1 if se._DB_CACHE else 0,
        "import_count" : len(se._IMPORT_CACHE or []),
    })


@app.route("/api/db-stats")
def api_db_stats():
    import scraper_engine as se
    db = se._load_database()
    total_coupons = sum(len(v) for k, v in db.items() if k != "_meta")
    return jsonify({
        "total_stores"  : len(db) - 1,
        "total_coupons" : total_coupons,
        "import_files"  : len(list_imports()),
        "import_records": sum(f["records"] for f in list_imports()),
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  AI COUPON FINDER v3 — Web App")
    print("  http://localhost:5000")
    print("=" * 60)
    app.run(debug=False, host="0.0.0.0", port=5000)
