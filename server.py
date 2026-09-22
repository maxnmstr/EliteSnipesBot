import json
import os

import requests
from flask import Flask, request

app = Flask(__name__)

# Setze diese als Umgebungsvariablen auf deinem Hosting (Render/Railway/etc.),
# NICHT hier im Klartext im Code lassen wenn das Repo geteilt wird.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "DEIN_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "DEINE_CHAT_ID")
# Optionaler simpler Schutz, damit nicht irgendwer deinen Webhook aufrufen kann.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except requests.RequestException:
        return False


def format_message(data: dict) -> str:
    t = data.get("type", "")
    symbol = data.get("symbol", "")
    tf = data.get("tf", "")
    direction = data.get("dir", "")
    arrow = "🟢 LONG" if direction == "LONG" else "🔴 SHORT"

    if t == "entry":
        return (
            f"🆕 <b>New Signal</b> — {symbol} ({tf})\n"
            f"{arrow}\n\n"
            f"🎯 Entry: {data.get('entry')}\n"
            f"🛑 SL (Invalidation): {data.get('sl')}\n"
            f"✅ TP1: {data.get('tp1')}\n"
            f"✅ TP2: {data.get('tp2')}\n"
            f"✅ TP3: {data.get('tp3')}"
        )
    if t in ("tp1", "tp2", "tp3"):
        label = t.upper()
        return (
            f"✅ <b>{label} hit</b> — {symbol} ({tf})\n"
            f"{arrow}\n"
            f"Price: {data.get('price')}"
        )
    if t == "sl":
        return (
            f"🛑 <b>SL hit</b> — {symbol} ({tf})\n"
            f"{arrow}\n"
            f"Price: {data.get('price')}"
        )
    return f"⚠️ Unknown alert type: {json.dumps(data)}"


@app.route("/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET:
        if request.args.get("secret") != WEBHOOK_SECRET:
            return {"error": "unauthorized"}, 401

    raw = request.get_data(as_text=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "invalid json", "raw": raw}, 400

    msg = format_message(data)
    ok = send_telegram(msg)
    return {"sent": ok}, (200 if ok else 500)


@app.route("/", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
