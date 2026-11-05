"""IR transmitters. A laptop has no IR LED, so a Wi-Fi IR blaster is needed."""

import logging

import panasonic_ir

log = logging.getLogger("ac.sender")


class DemoSender:
    """Prints the frame instead of sending it. Use to try the UI without hardware."""

    name = "demo"

    def status(self):
        return {"backend": self.name, "connected": True,
                "info": "Demo mode - no IR is sent. Set BROADLINK_HOST to use a real blaster."}

    def send(self, state):
        log.info("[DEMO] would send: %s", panasonic_ir.to_hex(state))


class BroadlinkSender:
    """Sends IR through a Broadlink RM4 mini / RM4 Pro / RM mini 3 on your Wi-Fi."""

    name = "broadlink"

    def __init__(self, host=None):
        self.host = host
        self.device = None
        self.error = None

    def _connect(self):
        import broadlink

        if self.device is not None:
            return self.device
        try:
            if self.host:
                device = broadlink.hello(self.host)
            else:
                found = broadlink.discover(timeout=5)
                if not found:
                    raise RuntimeError("No Broadlink device found on the network")
                device = found[0]
            device.auth()
            self.device = device
            self.error = None
            log.info("Connected to Broadlink %s at %s", device.model, device.host[0])
        except Exception as exc:
            self.error = str(exc)
            raise
        return self.device

    def status(self):
        try:
            d = self._connect()
            return {"backend": self.name, "connected": True,
                    "info": f"{d.manufacturer} {d.model} at {d.host[0]}"}
        except Exception as exc:
            return {"backend": self.name, "connected": False, "info": str(exc)}

    def send(self, state):
        packet = panasonic_ir.timings_to_broadlink(panasonic_ir.state_to_timings(state))
        try:
            self._connect().send_data(packet)
        except Exception:
            # Device may have rebooted or changed IP; reconnect once and retry.
            self.device = None
            self._connect().send_data(packet)


class AudioSender:
    """DIY IR blaster on the laptop's headphone jack.

    Wire two IR LEDs in anti-parallel between the LEFT and RIGHT pins of a 3.5mm
    plug. Left plays a sine at half the carrier, right plays it inverted, so each
    LED lights on alternate half-cycles -> the LEDs blink at the full carrier
    frequency (~36.7 kHz) during IR "marks" and stay dark during "spaces".
    """

    name = "audio"

    def __init__(self, device=None, rate=48000):
        self.device = int(device) if device and str(device).isdigit() else device
        self.rate = int(rate)

    def waveform(self, timings):
        import numpy as np

        freq = panasonic_ir.CARRIER_HZ / 2
        chunks = []
        for i, us in enumerate(timings):
            n = int(round(us * self.rate / 1_000_000))
            if i % 2 == 0:  # mark
                t = np.arange(n) / self.rate
                chunks.append(np.sin(2 * np.pi * freq * t))
            else:  # space
                chunks.append(np.zeros(n))
        left = np.concatenate(chunks).astype("float32")
        return np.column_stack([left, -left])

    def status(self):
        try:
            import sounddevice as sd

            dev = sd.query_devices(self.device, "output")
            return {"backend": self.name, "connected": True,
                    "info": f"Headphone-jack IR via '{dev['name']}' @ {self.rate} Hz "
                            "(keep volume at 100%)"}
        except Exception as exc:
            return {"backend": self.name, "connected": False, "info": str(exc)}

    def send(self, state):
        import sounddevice as sd

        wave = self.waveform(panasonic_ir.state_to_timings(state))
        sd.play(wave, self.rate, device=self.device, blocking=True)


class TermuxSender:
    """Runs on an Android phone with a built-in IR blaster, inside Termux.

    Needs the Termux:API app plus `pkg install termux-api`.
    """

    name = "phone"

    def pattern(self, state):
        timings = panasonic_ir.state_to_timings(state)[:-1]  # drop trailing gap
        return ",".join(str(t) for t in timings)

    def status(self):
        import shutil

        if shutil.which("termux-infrared-transmit"):
            return {"backend": self.name, "connected": True,
                    "info": "Phone IR blaster via Termux:API"}
        return {"backend": self.name, "connected": False,
                "info": "termux-infrared-transmit not found - install Termux:API app and `pkg install termux-api`"}

    def send(self, state):
        import subprocess

        result = subprocess.run(
            ["termux-infrared-transmit", "-f", str(panasonic_ir.CARRIER_HZ), self.pattern(state)],
            capture_output=True, text=True, timeout=15)
        if result.returncode != 0 or result.stderr.strip():
            raise RuntimeError(result.stderr.strip() or "IR transmit failed")


def discover(timeout=5):
    import broadlink

    return [{"host": d.host[0], "model": d.model, "type": d.devtype}
            for d in broadlink.discover(timeout=timeout)]
