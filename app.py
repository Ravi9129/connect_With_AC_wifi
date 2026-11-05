"""Panasonic AC control bot - Flask web remote.

Run:  python app.py   then open http://<this-pc-ip>:5000 on any phone/laptop.
Env:  AC_BACKEND=broadlink|phone|audio|demo   BROADLINK_HOST=192.168.x.x (optional)
      AUDIO_DEVICE=<sounddevice index/name> AUDIO_RATE=48000 (for audio backend)
"""

import json
import logging
import os
import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import panasonic_ir
import senders

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("ac")

STATE_FILE = Path(__file__).with_name("ac_state.json")
DEFAULT_SETTINGS = {
    "power": False, "mode": "cool", "temp": 24, "fan": "auto",
    "swing_v": "auto", "swing_h": "auto", "powerful": False, "quiet": False,
}

app = Flask(__name__)

backend = os.environ.get("AC_BACKEND", "broadlink" if os.environ.get("BROADLINK_HOST") else "demo")
if backend == "broadlink":
    sender = senders.BroadlinkSender(os.environ.get("BROADLINK_HOST"))
elif backend == "phone":
    sender = senders.TermuxSender()
elif backend == "audio":
    sender = senders.AudioSender(os.environ.get("AUDIO_DEVICE"), os.environ.get("AUDIO_RATE", 48000))
else:
    sender = senders.DemoSender()


def load_settings():
    try:
        return {**DEFAULT_SETTINGS, **json.loads(STATE_FILE.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    STATE_FILE.write_text(json.dumps(settings, indent=2))


def apply(changes):
    """Merge changes into the current settings, send IR, and persist."""
    settings = {**load_settings(), **changes}
    settings["temp"] = max(panasonic_ir.MIN_TEMP, min(panasonic_ir.MAX_TEMP, int(settings["temp"])))
    settings["fan"] = str(settings["fan"])
    settings["swing_v"] = str(settings["swing_v"])
    state = panasonic_ir.build_state(**settings)
    sender.send(state)
    save_settings(settings)
    return settings, panasonic_ir.to_hex(state)


def parse_command(text):
    """Turn a chat message like 'cool 22 fan 3' into setting changes."""
    t = text.lower().strip()
    changes = {}
    replies = []

    if re.search(r"\b(off|band|stop|shut)\b", t):
        return {"power": False}, "Turning the AC off."
    if re.search(r"\b(on|start|chalu)\b", t):
        changes["power"] = True

    for mode in panasonic_ir.MODES:
        # "fan 3" sets fan speed; fan *mode* needs "fan mode" / "fan only".
        pattern = r"\bfan\s*(mode|only)\b" if mode == "fan" else rf"\b{mode}\b"
        if re.search(pattern, t):
            changes["mode"] = mode
            changes["power"] = True

    current = load_settings()
    if m := re.search(r"\b(1[6-9]|2\d|30)\b(?!\s*%)", t):
        changes["temp"] = int(m.group(1))
    elif re.search(r"\b(colder|cooler|down|kam)\b", t):
        changes["temp"] = current["temp"] - 1
    elif re.search(r"\b(warmer|hotter|up|zyada)\b", t):
        changes["temp"] = current["temp"] + 1

    if m := re.search(r"\bfan\s*(auto|[1-5])\b", t):
        changes["fan"] = m.group(1)
    if m := re.search(r"\bswing\s*(auto|[1-5])\b", t):
        changes["swing_v"] = m.group(1)
    if "powerful" in t or "turbo" in t:
        changes.update(powerful=True, quiet=False)
    if "quiet" in t or "silent" in t:
        changes.update(quiet=True, powerful=False)
    if "normal" in t:
        changes.update(quiet=False, powerful=False)

    if not changes:
        return None, ("Sorry, I didn't get that. Try: 'on', 'off', 'cool 22', "
                      "'fan 3', 'swing auto', 'colder', 'powerful', 'dry 25'.")

    for key, val in changes.items():
        replies.append(f"{key}={val}")
    return changes, "OK: " + ", ".join(replies)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def get_state():
    return jsonify(settings=load_settings(), device=sender.status(),
                   options={"modes": list(panasonic_ir.MODES), "fans": list(panasonic_ir.FANS),
                            "swing_v": list(panasonic_ir.SWING_V), "swing_h": list(panasonic_ir.SWING_H),
                            "min_temp": panasonic_ir.MIN_TEMP, "max_temp": panasonic_ir.MAX_TEMP})


@app.post("/api/state")
def set_state():
    changes = {k: v for k, v in (request.get_json(silent=True) or {}).items() if k in DEFAULT_SETTINGS}
    try:
        settings, frame = apply(changes)
    except Exception as exc:
        log.exception("send failed")
        return jsonify(error=str(exc)), 500
    return jsonify(settings=settings, frame=frame)


@app.post("/api/bot")
def bot():
    text = (request.get_json(silent=True) or {}).get("message", "")
    changes, reply = parse_command(text)
    if changes is None:
        return jsonify(reply=reply, settings=load_settings())
    try:
        settings, _ = apply(changes)
    except Exception as exc:
        log.exception("send failed")
        return jsonify(reply=f"Couldn't reach the IR blaster: {exc}", settings=load_settings()), 500
    return jsonify(reply=reply, settings=settings)


@app.get("/api/discover")
def discover():
    try:
        return jsonify(devices=senders.discover())
    except Exception as exc:
        return jsonify(error=str(exc)), 500


if __name__ == "__main__":
    log.info("Backend: %s", sender.name)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
