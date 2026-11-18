"""Register definitions for the Vents AHU UDP protocol."""

from typing import Literal, NotRequired, TypedDict

FmtTag = type[int] | type[bool] | type[float] | type[str] | Literal["ip", "raw"]
EndianTag = Literal["big", "little"]


class Register(TypedDict):
    name: NotRequired[str]
    parameter: bytes  # 2-byte BE code (e.g., b"\x00\x02")
    count: int
    fmt: FmtTag
    read_only: NotRequired[bool]
    write_only: NotRequired[bool]
    min: NotRequired[int]
    max: NotRequired[int]
    scale: NotRequired[float]
    endian: NotRequired[EndianTag]
    signed: NotRequired[bool]


# Read/Write
POWER_ON: Register = {
    "parameter": b"\x00\x01",
    "count": 1,
    "fmt": bool,
    "name": "power_on",
    "min": 0,
    "max": 1,
}
MODE: Register = {
    "parameter": b"\x00\x0e",
    "count": 1,
    "fmt": int,
    "name": "mode",
    "min": 0,
    "max": 3,
}
SPEED: Register = {
    "parameter": b"\x00\x02",
    "count": 1,
    "fmt": int,
    "name": "speed",
    "min": 1,
    "max": 3,
}
TARGET_TEMP: Register = {
    "parameter": b"\x00\x18",
    "count": 1,
    "fmt": int,
    "name": "target_temp",
    "min": 15,
    "max": 30,
}
SUPPLY_FAN_SPEED_1: Register = {
    "parameter": b"\x00\x3a",
    "count": 1,
    "fmt": int,
    "name": "supply_fan_speed_1",
    "min": 0,
    "max": 100,
}
SUPPLY_FAN_SPEED_2: Register = {
    "parameter": b"\x00\x3c",
    "count": 1,
    "fmt": int,
    "name": "supply_fan_speed_2",
    "min": 0,
    "max": 100,
}
SUPPLY_FAN_SPEED_3: Register = {
    "parameter": b"\x00\x3e",
    "count": 1,
    "fmt": int,
    "name": "supply_fan_speed_3",
    "min": 0,
    "max": 100,
}
EXHAUST_FAN_SPEED_1: Register = {
    "parameter": b"\x00\x3b",
    "count": 1,
    "fmt": int,
    "name": "exhaust_fan_speed_1",
    "min": 0,
    "max": 100,
}
EXHAUST_FAN_SPEED_2: Register = {
    "parameter": b"\x00\x3d",
    "count": 1,
    "fmt": int,
    "name": "exhaust_fan_speed_2",
    "min": 0,
    "max": 100,
}
EXHAUST_FAN_SPEED_3: Register = {
    "parameter": b"\x00\x3f",
    "count": 1,
    "fmt": int,
    "name": "exhaust_fan_speed_3",
    "min": 0,
    "max": 100,
}

# Read-only
BOOST_MODE: Register = {
    "parameter": b"\x00\x06",
    "count": 1,
    "fmt": bool,
    "name": "boost_mode",
    "read_only": True,
}
CURRENT_HUMIDITY: Register = {
    "parameter": b"\x00\x25",
    "count": 1,
    "fmt": int,
    "name": "current_humidity",
    "read_only": True,
}
EXHAUST_IN_TEMPERATURE: Register = {
    "parameter": b"\x00\x1f",
    "count": 2,
    "fmt": float,
    "name": "exhaust_in_temperature",
    "read_only": True,
    "scale": 0.1,
    "endian": "little",
    "signed": True,
}
SUPPLY_OUT_TEMPERATURE: Register = {
    "parameter": b"\x00\x1e",
    "count": 2,
    "fmt": float,
    "name": "supply_out_temperature",
    "read_only": True,
    "scale": 0.1,
    "endian": "little",
    "signed": True,
}
SUPPLY_IN_TEMPERATURE: Register = {
    "parameter": b"\x00\x21",
    "count": 2,
    "fmt": float,
    "name": "supply_in_temperature",
    "read_only": True,
    "scale": 0.1,
    "endian": "little",
    "signed": True,
}
EXHAUST_OUT_TEMPERATURE: Register = {
    "parameter": b"\x00\x22",
    "count": 2,
    "fmt": float,
    "name": "exhaust_out_temperature",
    "read_only": True,
    "scale": 0.1,
    "endian": "little",
    "signed": True,
}
FAN1_SPEED: Register = {
    "parameter": b"\x00\x4a",
    "count": 2,
    "fmt": int,
    "name": "fan1_speed",
    "read_only": True,
    "endian": "little",
}
FAN2_SPEED: Register = {
    "parameter": b"\x00\x4b",
    "count": 2,
    "fmt": int,
    "name": "fan2_speed",
    "read_only": True,
    "endian": "little",
}
ALARM_INDICATOR: Register = {
    "parameter": b"\x00\x83",
    "count": 1,
    "fmt": bool,
    "name": "alarm_indicator",
    "read_only": True,
}
# The device may pad [minutes, hours, days] with a trailing byte.
FILTER_TIMER_COUNTDOWN: Register = {
    "parameter": b"\x00\x64",
    "count": 3,
    "fmt": "raw",
    "name": "filter_timer_countdown",
    "read_only": True,
}
FILTER_REPLACEMENT_INDICATOR: Register = {
    "parameter": b"\x00\x88",
    "count": 1,
    "fmt": bool,
    "name": "filter_indicator",
    "read_only": True,
}
# The unit does not acknowledge trigger writes.
FILTER_TIMER_RESET: Register = {
    "parameter": b"\x00\x65",
    "count": 1,
    "fmt": int,
    "name": "filter_timer_reset",
    "write_only": True,
}
RESET_ALARMS: Register = {
    "parameter": b"\x00\x80",
    "count": 1,
    "fmt": int,
    "name": "reset_alarms",
    "write_only": True,
}
