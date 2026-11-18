"""Synthetic UDP reply frames shared by the codec and transport tests."""

DEVICE = b"0000000000000000"
PASSWORD = b"1111"


def reply(body, *, device=DEVICE, function=b"\x06"):
    frame = b"\xfd\xfd\x03\x10" + device + b"\x04" + PASSWORD + function + body
    return frame + (sum(frame[2:]) & 0xFFFF).to_bytes(2, "little")
