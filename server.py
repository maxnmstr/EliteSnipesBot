import os
import json

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]      # Token von @BotFather
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]          # ID der Telegram-Gruppe/des Kanals
WEBHOOK_KEY = os.environ.get("WEBHOOK_KEY")       # optional: Schutz gegen fremde Aufrufe

# Merkt sich pro Signal-ID die Telegram-Nachricht, damit TP/SL-Meldungen als Antwort darauf erscheinen.
# Hinweis: Geht bei einem Neustart des Servers verloren (die Meldungen kommen dann ohne Verknüpfung).
signal_msgs = {}


def tf_label(tf: str) -> str:
    mapping = {"1": "M1", "5": "M5", "15": "M15", "30": "M30", "60": "H1", "240": "H4", "D": "D1"}
    return mapping.get(str(tf), str(tf))


def fmt(x) -> str:
    return f"{float(x):.2f}"


def trade_no(symbol: str, tf: str, no) -> str:
    """Trade-Nummer im Format Symbol/Timeframe/#Nr. des Tages, z. B. XAUUSD/M15/#3.
    Die Tageszählung kommt direkt vom Indikator und bleibt daher auch nach einem Server-Neustart korrekt."""
    return f"{symbol}/{tf}/#{no if no is not None else '?'}"


def send(text: str, reply_to: int | None = None) -> int | None:
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to
        payload["allow_sending_without_reply"] = True
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10)
    if not r.ok:
        print("Telegram error:", r.status_code, r.text)
        return None
    return r.json()["result"]["message_id"]


@app.route("/", methods=["GET"])
def health():
    return "ok", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_KEY and request.args.get("key") != WEBHOOK_KEY:
        return "forbidden", 403

    raw = request.get_data(as_text=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Invalid JSON:", raw)
        return "bad json", 400

    typ = data.get("type", "signal")
    sig_id = str(data.get("id", ""))
    symbol = data.get("symbol", "?")
    tf = tf_label(data.get("timeframe", "?"))
    side = data.get("side", "?")
    arrow = "🟢" if side == "LONG" else "🔴"
    no = trade_no(symbol, tf, data.get("no"))

    if typ == "signal":
        text = (
            f"{arrow} <b>{side} {symbol}</b> ({tf})\n"
            f"🔖 Trade <b>{no}</b>\n\n"
            f"📍 Entry: <b>{fmt(data['entry'])}</b>\n"
            f"🛑 SL: {fmt(data['sl'])}\n\n"
            f"🎯 TP1: {fmt(data['tp1'])}\n"
            f"🎯 TP2: {fmt(data['tp2'])}\n"
            f"🎯 TP3: {fmt(data['tp3'])}\n"
            f"🎯 TP4: {fmt(data['tp4'])}\n"
            f"🎯 TP5: {fmt(data['tp5'])}"
        )
        msg_id = send(text)
        if msg_id and sig_id:
            signal_msgs[sig_id] = msg_id

    elif typ == "tp":
        tp = data.get("tp", "?")
        text = f"✅ <b>{no}: TP{tp} hit</b>\n{side} {symbol} ({tf}) · Price: {fmt(data['price'])}"
        send(text, reply_to=signal_msgs.get(sig_id))

    elif typ == "sl":
        text = f"❌ <b>{no}: SL hit</b>\n{side} {symbol} ({tf}) · Price: {fmt(data['price'])}"
        send(text, reply_to=signal_msgs.get(sig_id))
        signal_msgs.pop(sig_id, None)

    else:
        print("Unknown type:", data)

    return jsonify(ok=True), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
