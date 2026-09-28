import os
import json
import logging

import requests
from flask import Flask, request

# ───────────────────────── Setup ─────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("elitesnipes")

# Token und Chat-ID kommen aus den Render-Umgebungsvariablen (Environment), NICHT aus dem Code
TELEGRAM_TOKEN = (
    os.environ.get("TELEGRAM_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
    or os.environ.get("BOT_TOKEN")
)
CHAT_ID = os.environ.get("CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    log.error("TELEGRAM_TOKEN oder CHAT_ID fehlt – in Render unter Environment eintragen!")

app = Flask(__name__)


# ───────────────────────── Telegram ─────────────────────────
def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        log.error("Kann nicht senden: Token oder Chat-ID fehlt")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        if r.status_code != 200:
            log.error("Telegram-Fehler %s: %s", r.status_code, r.text)
            return False
        return True
    except Exception as e:
        log.exception("Telegram-Request fehlgeschlagen: %s", e)
        return False


# ───────────────────────── Fallback für Alerts ohne "text" ─────────────────────────
def build_fallback_message(data: dict) -> str:
    side = str(data.get("side") or data.get("action") or "").upper()
    symbol = data.get("symbol") or data.get("ticker") or ""
    lines = [f"{'🟢' if side == 'BUY' else '🔴' if side == 'SELL' else '📣'} {side} {symbol}".strip()]
    for key, label in [("entry", "Entry"), ("sl", "SL"), ("tp1", "TP1"), ("tp2", "TP2"),
                       ("tp3", "TP3"), ("tp4", "TP4"), ("tp5", "TP5"), ("price", "Preis")]:
        if data.get(key) not in (None, ""):
            lines.append(f"{label}: {data[key]}")
    if len(lines) == 1:
        lines.append(json.dumps(data, ensure_ascii=False))
    return "\n".join(lines)


# ───────────────────────── Routes ─────────────────────────
@app.route("/", methods=["GET"])
def health():
    # Für Render-Healthcheck bzw. UptimeRobot (hält den Server wach)
    return "Elite Snipes Bot läuft", 200


@app.route("/", methods=["POST"])
@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data(as_text=True) or ""
    log.info("Webhook empfangen: %s", raw[:500])

    data = request.get_json(force=True, silent=True)

    # Kein JSON → Text so weiterleiten, wie er kommt
    if not isinstance(data, dict):
        if raw.strip():
            send_telegram(raw.strip())
            return "ok", 200
        return "leer", 400

    # SLE-Scanner: fertiger Telegram-Text im Feld "text"
    text = data.get("text")
    if text:
        send_telegram(str(text))
        return "ok", 200

    # Andere/alte Alerts: Nachricht aus den Feldern bauen
    send_telegram(build_fallback_message(data))
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
