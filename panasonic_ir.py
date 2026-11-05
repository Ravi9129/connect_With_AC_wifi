"""Panasonic AC infrared protocol encoder.

Builds the 27-byte Panasonic AC state frame and converts it to raw IR
timings (microseconds). Based on the publicly documented protocol used by
most Panasonic split ACs (remotes like A75C2xxx / A75C3xxx / A75C4xxx).
"""

# Timings in microseconds
CARRIER_HZ = 36700
HDR_MARK = 3456
HDR_SPACE = 1728
BIT_MARK = 432
ONE_SPACE = 1296
ZERO_SPACE = 432
SECTION_GAP = 10000
MESSAGE_GAP = 100000

SECTION1_LEN = 8
STATE_LEN = 27
CHECKSUM_INIT = 0xF4

MODES = {"auto": 0x0, "dry": 0x2, "cool": 0x3, "heat": 0x4, "fan": 0x6}
# Fan: auto, or speed 1 (lowest) .. 5 (highest)
FANS = {"auto": 0xA, "1": 0x3, "2": 0x4, "3": 0x5, "4": 0x6, "5": 0x7}
# Vertical swing: auto, or fixed position 1 (highest) .. 5 (lowest)
SWING_V = {"auto": 0xF, "1": 0x1, "2": 0x2, "3": 0x3, "4": 0x4, "5": 0x5}
SWING_H = {"auto": 0xD, "middle": 0x6, "left": 0x9, "left_max": 0xC,
           "right": 0xA, "right_max": 0xB}

MIN_TEMP = 16
MAX_TEMP = 30

DEFAULT_STATE = [
    0x02, 0x20, 0xE0, 0x04, 0x00, 0x00, 0x00, 0x06,
    0x02, 0x20, 0xE0, 0x04, 0x00, 0x08, 0x34, 0x80,
    0xAF, 0x0D, 0x00, 0x0E, 0xE0, 0x00, 0x00, 0x89,
    0x00, 0x00, 0x00,
]


def build_state(power=True, mode="cool", temp=24, fan="auto",
                swing_v="auto", swing_h="auto", powerful=False, quiet=False):
    """Return the 27-byte frame for the requested AC settings."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}")
    if str(fan) not in FANS:
        raise ValueError(f"fan must be one of {list(FANS)}")
    if str(swing_v) not in SWING_V:
        raise ValueError(f"swing_v must be one of {list(SWING_V)}")
    if swing_h not in SWING_H:
        raise ValueError(f"swing_h must be one of {list(SWING_H)}")

    temp = max(MIN_TEMP, min(MAX_TEMP, int(temp)))
    state = list(DEFAULT_STATE)

    state[13] = (MODES[mode] << 4) | 0x08 | (0x01 if power else 0x00)
    state[14] = temp << 1
    state[16] = (FANS[str(fan)] << 4) | SWING_V[str(swing_v)]
    state[17] = SWING_H[swing_h]
    state[21] = (0x01 if powerful else 0x00) | (0x20 if quiet and not powerful else 0x00)
    state[26] = (sum(state[SECTION1_LEN:STATE_LEN - 1]) + CHECKSUM_INIT) & 0xFF
    return state


def _encode_bytes(data):
    pulses = [HDR_MARK, HDR_SPACE]
    for byte in data:
        for bit in range(8):  # LSB first
            pulses.append(BIT_MARK)
            pulses.append(ONE_SPACE if (byte >> bit) & 1 else ZERO_SPACE)
    pulses.append(BIT_MARK)
    return pulses


def state_to_timings(state):
    """Convert a frame into alternating mark/space durations (µs)."""
    timings = _encode_bytes(state[:SECTION1_LEN])
    timings.append(SECTION_GAP)
    timings += _encode_bytes(state[SECTION1_LEN:])
    timings.append(MESSAGE_GAP)
    return timings


def timings_to_broadlink(timings):
    """Pack raw timings into a Broadlink IR packet."""
    unit = 8192 / 269  # µs -> Broadlink ticks (~32.84 µs per tick)
    body = bytearray()
    for t in timings:
        ticks = int(round(t / unit))
        if ticks < 256:
            body.append(ticks)
        else:
            body += bytes([0x00, ticks >> 8, ticks & 0xFF])
    body += bytes([0x0D, 0x05])

    packet = bytearray([0x26, 0x00]) + len(body).to_bytes(2, "little") + body
    packet += bytes((16 - len(packet) % 16) % 16)
    return bytes(packet)


def to_hex(state):
    return " ".join(f"{b:02X}" for b in state)
