import pytest

from aiovents import VentsError, VentsValueError
from aiovents.codec import (
    build_body,
    build_frame,
    decode_reply,
    encode_write,
    extract_inner,
    filter_days,
    format_value,
    normalize_device_id,
    trigger_body,
)
from aiovents.registers import (
    FILTER_TIMER_COUNTDOWN,
    FILTER_TIMER_RESET,
    POWER_ON,
    SUPPLY_FAN_SPEED_1,
    SUPPLY_IN_TEMPERATURE,
    TARGET_TEMP,
    Register,
)

from .wire import DEVICE, PASSWORD, reply


def test_frame_and_paged_body_match_wire_format():
    body, keys = build_body([b"\x00\x21", b"\x01\x42", b"\x00\x01"])
    assert body == bytes.fromhex("21 ff 01 42 ff 00 01")
    assert keys == {(0, 0x21), (1, 0x42), (0, 0x01)}
    assert build_frame(DEVICE, PASSWORD, b"\x01", b"\x01") == (
        b"\xfd\xfd\x03\x10" + DEVICE + b"\x04" + PASSWORD + b"\x01\x01\xdd\x03"
    )
    trigger: Register = {
        "parameter": b"\x01\x65",
        "count": 1,
        "fmt": int,
        "write_only": True,
    }
    assert trigger_body(trigger) == bytes.fromhex("ff 01 65 01")


def test_decode_envelope_markers_and_pages():
    body = bytes.fromhex("01 01 ff 01 fc 03 fd 42 fe 02 43 9c ff ff 00 02 03")
    assert decode_reply(extract_inner(b"VentIP" + reply(body)), DEVICE) == {
        (0, 1): b"\x01",
        (1, 0x42): None,
        (1, 0x43): b"\x9c\xff",
        (0, 2): b"\x03",
    }


@pytest.mark.parametrize("body", ["01", "ff", "fc", "fd", "fe 01", "fe 02 43 01"])
def test_decode_rejects_truncated_parameters(body):
    with pytest.raises(VentsError, match="Truncated"):
        decode_reply(reply(bytes.fromhex(body)), DEVICE)


@pytest.mark.parametrize(
    ("frame", "error"),
    [
        (b"\xfd\xfd", "Invalid response header"),
        (reply(b"\x01\x01", device=b"1111111111111111"), "another device"),
        (reply(b"\x01\x01", function=b"\x01"), "response function"),
        (reply(b"\x01\x01")[:-1] + b"\x00", "Checksum mismatch"),
    ],
)
def test_decode_rejects_invalid_frames(frame, error):
    with pytest.raises(VentsError, match=error):
        decode_reply(frame, DEVICE)


@pytest.mark.parametrize(
    ("reg", "raw", "expected"),
    [
        (SUPPLY_IN_TEMPERATURE, b"\x9c\xff", -10.0),
        (SUPPLY_IN_TEMPERATURE, b"\x06\x01", 26.2),
        (POWER_ON, b"\x01", True),
        (POWER_ON, b"\x00", False),
        (FILTER_TIMER_COUNTDOWN, b"\x01\x02\x03\x00", b"\x01\x02\x03"),
    ],
)
def test_formats_values(reg, raw, expected):
    value = format_value(reg, raw)
    assert value == expected
    assert type(value) is type(expected)


def test_rejects_short_value_and_reads_padded_countdown():
    assert filter_days(b"\x01\x02\x03\xff") == 3
    with pytest.raises(VentsError, match="Short value"):
        filter_days(b"\x01\x02")


@pytest.mark.parametrize("value", [0, 100])
def test_encodes_write_at_bounds(value):
    assert encode_write(SUPPLY_FAN_SPEED_1, value) == value


@pytest.mark.parametrize(
    ("reg", "value", "error"),
    [
        (SUPPLY_FAN_SPEED_1, -1, "min"),
        (SUPPLY_FAN_SPEED_1, 101, "max"),
        (TARGET_TEMP, 20.5, "must be int"),
        (POWER_ON, 2, "max"),
        (SUPPLY_IN_TEMPERATURE, 20, "read-only"),
        (FILTER_TIMER_RESET, 1, "write-only"),
        ({"parameter": b"\x00\x21", "count": 2, "fmt": int}, 20, "1-byte"),
    ],
)
def test_rejects_invalid_write(reg, value, error):
    with pytest.raises(VentsValueError, match=error):
        encode_write(reg, value)


@pytest.mark.parametrize("device", ["", "x" * 17, "démo"])
def test_invalid_device_id_rejected(device):
    with pytest.raises(VentsValueError, match="ASCII"):
        normalize_device_id(device)


def test_device_id_is_padded_without_changing_case():
    assert normalize_device_id("Fake-1") == "Fake-10000000000"
