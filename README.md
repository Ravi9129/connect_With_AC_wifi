# Panasonic AC Bot (Flask)

A web remote + chat bot for a Panasonic AC. Open it from any phone or laptop on your Wi-Fi.

## Important: you need an IR blaster

Panasonic ACs are controlled by **infrared light**. A laptop/PC has no IR LED, so Python
alone cannot reach the AC. You need one small device that sits in the room facing the AC:

| Option | Cost (approx) | Notes |
|---|---|---|
| **Broadlink RM4 mini** (recommended) | ₹1,200–1,800 | Wi-Fi IR blaster. This app supports it out of the box. |
| Broadlink RM4 Pro / RM mini 3 | similar | Also supported. |
| Universal AC remote | ₹200–400 | Simplest fix if you just want a remote again (no app). |

If your AC is a Wi-Fi model (Panasonic **MirAIe** app sticker on the indoor unit), you can
also use the MirAIe app on any Android/iPhone — no IR needed.

## Setup

```bash
cd ac
pip install -r requirements.txt
```

1. Set up the Broadlink once with the **Broadlink app** so it joins your Wi-Fi
   (when asked, you can skip adding it to the cloud / keep "local" control).
2. Find its IP: run the app and open `http://localhost:5000/api/discover`, or check your router.
3. Start the bot:

```powershell
$env:BROADLINK_HOST = "192.168.1.50"   # your blaster's IP
python app.py
```

Then open `http://<your-pc-ip>:5000` on your phone (same Wi-Fi). Find the PC IP with `ipconfig`.

Without `BROADLINK_HOST` the app runs in **demo mode**: the UI works but no IR is sent
(frames are printed in the console).

## Run the bot on an Android phone that has an IR blaster (e.g. Realme)

1. Check the phone has IR: look for the preinstalled **IR Remote** app, or a small dark
   dot on the top edge of the phone.
2. Install **Termux** and **Termux:API** from F-Droid (both from the same source; not the Play Store Termux).
3. In Termux:

```bash
pkg install python termux-api
pip install flask
```

4. Copy this `ac` folder to the phone (e.g. to `~/ac`), then:

```bash
cd ~/ac
AC_BACKEND=phone python app.py
```

5. Open `http://localhost:5000` in the phone's browser and point the phone's top edge at the AC.
   Other devices on the same Wi-Fi can use `http://<phone-ip>:5000`.

## DIY: laptop headphone jack as IR blaster (≈ ₹50)

Parts: 2 × 940 nm IR LEDs + an old earphone wire / 3.5 mm plug.

1. Cut the earphone wire. Find the **Left**, **Right** and **Ground** wires (ground is not used).
2. LED 1: long leg → Left, short leg → Right.
   LED 2: long leg → Right, short leg → Left (reversed / anti-parallel).
3. Plug into the laptop, set volume to **100%**, turn off Windows sound enhancements
   / Dolby, and point the LEDs at the AC from under 1 m.
4. Run:

```powershell
$env:AC_BACKEND = "audio"
python app.py
```

To pick a specific output, set `$env:AUDIO_DEVICE` to an index from
`python -m sounddevice`. Check that the LEDs are firing by watching them through a
phone camera (the front camera usually shows IR as a purple flicker).
Many laptop jacks output under the ~1.2 V an IR LED needs, so this does not work on every
laptop. If nothing happens, use a Broadlink or an ESP8266 + IR LED instead.

## Bot commands

`on`, `off`, `cool 22`, `heat 28`, `dry`, `fan 3`, `fan auto`, `swing auto`, `swing 2`,
`colder`, `warmer`, `powerful`, `quiet`, `normal`.

## Files

- `app.py` – Flask server, REST API (`/api/state`, `/api/bot`, `/api/discover`)
- `panasonic_ir.py` – Panasonic AC IR protocol encoder (state → IR timings → Broadlink packet)
- `senders.py` – Broadlink and demo transmitters
- `templates/index.html` – phone-friendly remote UI
