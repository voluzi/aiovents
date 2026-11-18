"""Encode requests and decode replies without opening a socket."""

from collections.abc import Sequence

from .const import PACKET_PREFIX, PROTOCOL_TYPE, RESPONSE, SIZE_ID
from .exceptions import VentsError, VentsValueError
from .registers import FILTER_TIMER_COUNTDOWN, Register

RegisterValue = int | float | bool | str | bytes
RegisterKey = tuple[int, int]
Reply = dict[RegisterKey, bytes | None]


def u16_le(value: int) -> bytes:
    return (value & 0xFFFF).to_bytes(2, "little")


def sum16(data: bytes) -> int:
    return sum(data) & 0xFFFF


def extract_inner(response: bytes) -> bytes:
    """Remove the optional VentIP transport envelope."""
    pos = response.find(PACKET_PREFIX)
    if pos < 0:
        raise VentsError("No packet prefix in response")
    return response[pos:]


def validate(inner: bytes, device_id: bytes | None = None) -> int:
    """Validate a response header and checksum; return the body offset."""
    if len(inner) < 8 or inner[:2] != PACKET_PREFIX:
        raise VentsError("Invalid response header")
    if inner[2:3] != PROTOCOL_TYPE:
        raise VentsError("Unexpected protocol type")
    end = len(inner) - 2
    id_end = 4 + inner[3]
    if id_end >= end:
        raise VentsError("Truncated device ID")
    if device_id is not None and inner[4:id_end] != device_id:
        raise VentsError("Response belongs to another device")
    function_pos = id_end + 1 + inner[id_end]
    if function_pos >= end:
        raise VentsError("Truncated response header")
    if inner[function_pos : function_pos + 1] != RESPONSE:
        raise VentsError("Unexpected response function")
    expect = int.from_bytes(inner[-2:], "little")
    calc = sum16(inner[2:-2])
    if calc != expect:
        raise VentsError(f"Checksum mismatch: calc=0x{calc:04x} expect=0x{expect:04x}")
    return function_pos + 1


def decode_reply(inner: bytes, device_id: bytes | None = None) -> Reply:
    pos = validate(inner, device_id)
    end = len(inner) - 2
    page = 0
    out: Reply = {}
    while pos < end:
        marker = inner[pos]
        if pos + 1 >= end:
            raise VentsError("Truncated response parameter")
        if marker == 0xFF:
            page = inner[pos + 1]
            pos += 2
        elif marker == 0xFC:
            pos += 2
        elif marker == 0xFD:
            out[(page, inner[pos + 1])] = None
            pos += 2
        elif marker == 0xFE:
            size = inner[pos + 1]
            value_start = pos + 3
            value_end = value_start + size
            if value_start > end or value_end > end:
                raise VentsError("Truncated multi-byte response parameter")
            out[(page, inner[pos + 2])] = inner[value_start:value_end]
            pos = value_end
        else:
            out[(page, marker)] = inner[pos + 1 : pos + 2]
            pos += 2
    return out


def normalize_device_id(device_id: str) -> str:
    """Validate and right-pad a device ID to its fixed width on the wire."""
    if not 1 <= len(device_id) <= 16 or not device_id.isascii():
        raise VentsValueError("Device ID must contain 1 to 16 ASCII characters")
    return device_id.ljust(16, "0")


def encode_password(password: str) -> bytes:
    """Validate the password and its one-byte length."""
    if not 1 <= len(password) <= 255 or not password.isascii():
        raise VentsValueError("Password must contain 1 to 255 ASCII characters")
    return password.encode("ascii")


def build_frame(
    device_id: bytes, password: bytes, function: bytes, body: bytes
) -> bytes:
    frame = PACKET_PREFIX + PROTOCOL_TYPE + SIZE_ID + device_id
    frame += bytes([len(password)]) + password + function + body
    return frame + u16_le(sum16(frame[2:]))


def build_body(
    codes: Sequence[bytes], value: int | None = None
) -> tuple[bytes, set[RegisterKey]]:
    body = bytearray()
    keys: set[RegisterKey] = set()
    page = 0
    if value is not None and not 0 <= value <= 255:
        raise VentsValueError("Only 1-byte compact writes supported")
    for code in codes:
        code_page, parameter = code
        if page != code_page:
            page = code_page
            body.extend((0xFF, page))
        body.append(parameter)
        if value is not None:
            body.append(value)
        keys.add((page, parameter))
    return bytes(body), keys


def register_name(reg: Register) -> str:
    return reg.get("name") or reg["parameter"].hex()


def trigger_body(reg: Register) -> bytes:
    if reg.get("read_only"):
        raise VentsValueError(f"Register '{register_name(reg)}' is read-only")
    if not reg.get("write_only"):
        raise VentsValueError(f"Register '{register_name(reg)}' is not a trigger")
    return build_body([reg["parameter"]], 1)[0]


def format_value(reg: Register, raw: bytes) -> RegisterValue:
    count = reg["count"]
    if len(raw) < count:
        raise VentsError(
            f"Short value for {register_name(reg)}: need {count}, got {len(raw)}"
        )
    raw = raw[:count]
    fmt = reg["fmt"]
    if fmt in (int, float, bool):
        value = int.from_bytes(
            raw, reg.get("endian", "big"), signed=reg.get("signed", False)
        )
        if fmt is bool:
            return bool(value)
        scaled = value * reg.get("scale", 1)
        return round(float(scaled), 1) if fmt is float else int(scaled)
    if fmt is str:
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError:
            return raw.hex()
    if fmt == "ip":
        return ".".join(str(byte) for byte in raw) if len(raw) == 4 else ""
    return raw


def encode_write(reg: Register, value: RegisterValue) -> int:
    if reg.get("read_only"):
        raise VentsValueError(f"Register '{register_name(reg)}' is read-only")
    if reg.get("write_only"):
        raise VentsValueError(
            f"Register '{register_name(reg)}' is a write-only trigger; "
            "use async_trigger()"
        )
    if reg["count"] != 1:
        raise VentsValueError("Only 1-byte compact writes supported")

    fmt = reg["fmt"]
    if fmt in (int, bool) and not isinstance(value, int):
        raise VentsValueError(f"Value must be int for fmt={fmt.__name__}")
    if isinstance(value, (int, float)):
        if "min" in reg and value < reg["min"]:
            raise VentsValueError(f"Value {value} < min {reg['min']}")
        if "max" in reg and value > reg["max"]:
            raise VentsValueError(f"Value {value} > max {reg['max']}")

    try:
        if fmt in (int, bool, float):
            number = (
                round(float(value) / reg.get("scale", 1.0))
                if fmt is float
                else int(value)
            )
            raw = number.to_bytes(1, signed=reg.get("signed", False))
        elif fmt is str and isinstance(value, str):
            raw = value.encode("ascii")
        elif fmt == "raw" and isinstance(value, bytes):
            raw = value
        else:
            raise TypeError(f"Unsupported register value for fmt={fmt!r}")
    except (ValueError, TypeError, OverflowError) as exc:
        raise VentsValueError(f"Invalid value for {register_name(reg)}: {exc}") from exc
    if len(raw) != 1:
        raise VentsValueError(f"Value length mismatch: need 1, got {len(raw)}")
    return raw[0]


def filter_days(raw: bytes) -> int:
    if len(raw) < FILTER_TIMER_COUNTDOWN["count"]:
        raise VentsError("Short value for filter_timer_countdown: need 3 bytes")
    return raw[2]
