"""Typed status and settings snapshots."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Self, TypeVar

from . import registers as reg
from .codec import RegisterValue, filter_days
from .exceptions import VentsError

STATUS_REGISTERS = (
    reg.POWER_ON,
    reg.MODE,
    reg.SPEED,
    reg.TARGET_TEMP,
    reg.SUPPLY_IN_TEMPERATURE,
    reg.SUPPLY_OUT_TEMPERATURE,
    reg.EXHAUST_IN_TEMPERATURE,
    reg.EXHAUST_OUT_TEMPERATURE,
    reg.CURRENT_HUMIDITY,
    reg.FAN1_SPEED,
    reg.FAN2_SPEED,
    reg.BOOST_MODE,
    reg.ALARM_INDICATOR,
    reg.FILTER_REPLACEMENT_INDICATOR,
    reg.FILTER_TIMER_COUNTDOWN,
)

SETTINGS_REGISTERS = (
    reg.SUPPLY_FAN_SPEED_1,
    reg.SUPPLY_FAN_SPEED_2,
    reg.SUPPLY_FAN_SPEED_3,
    reg.EXHAUST_FAN_SPEED_1,
    reg.EXHAUST_FAN_SPEED_2,
    reg.EXHAUST_FAN_SPEED_3,
)


class Mode(IntEnum):
    VENTILATION = 0
    HEATING = 1
    COOLING = 2
    AUTO = 3


class FanSpeed(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


T = TypeVar("T")
E = TypeVar("E", bound=IntEnum)

Values = Mapping[str, RegisterValue | None]


def _convert(kind: type[T], value: RegisterValue | None) -> T | None:
    return value if isinstance(value, kind) else None


def _as_enum(kind: type[E], value: RegisterValue | None) -> E | None:
    if isinstance(value, int):
        try:
            return kind(value)
        except ValueError:
            pass
    return None


def _countdown(value: RegisterValue | None) -> int | None:
    if isinstance(value, bytes):
        try:
            return filter_days(value)
        except VentsError:
            pass
    return None


@dataclass(frozen=True, slots=True)
class VentsStatus:
    power_on: bool | None = None
    mode: Mode | None = None
    speed: FanSpeed | None = None
    target_temp: int | None = None
    supply_in_temperature: float | None = None
    supply_out_temperature: float | None = None
    exhaust_in_temperature: float | None = None
    exhaust_out_temperature: float | None = None
    current_humidity: int | None = None
    fan1_speed: int | None = None
    fan2_speed: int | None = None
    boost_mode: bool | None = None
    alarm_indicator: bool | None = None
    filter_indicator: bool | None = None
    filter_days_remaining: int | None = None

    @classmethod
    def from_values(cls, values: Values) -> Self:
        return cls().updated(values)

    def updated(self, values: Values) -> Self:
        return replace(
            self,
            power_on=_convert(bool, values.get("power_on", self.power_on)),
            mode=_as_enum(Mode, values["mode"]) if "mode" in values else self.mode,
            speed=_as_enum(FanSpeed, values.get("speed", self.speed)),
            target_temp=_convert(int, values.get("target_temp", self.target_temp)),
            supply_in_temperature=_convert(
                float, values.get("supply_in_temperature", self.supply_in_temperature)
            ),
            supply_out_temperature=_convert(
                float, values.get("supply_out_temperature", self.supply_out_temperature)
            ),
            exhaust_in_temperature=_convert(
                float, values.get("exhaust_in_temperature", self.exhaust_in_temperature)
            ),
            exhaust_out_temperature=_convert(
                float,
                values.get("exhaust_out_temperature", self.exhaust_out_temperature),
            ),
            current_humidity=_convert(
                int, values.get("current_humidity", self.current_humidity)
            ),
            fan1_speed=_convert(int, values.get("fan1_speed", self.fan1_speed)),
            fan2_speed=_convert(int, values.get("fan2_speed", self.fan2_speed)),
            boost_mode=_convert(bool, values.get("boost_mode", self.boost_mode)),
            alarm_indicator=_convert(
                bool, values.get("alarm_indicator", self.alarm_indicator)
            ),
            filter_indicator=_convert(
                bool, values.get("filter_indicator", self.filter_indicator)
            ),
            filter_days_remaining=_countdown(values["filter_timer_countdown"])
            if "filter_timer_countdown" in values
            else self.filter_days_remaining,
        )


@dataclass(frozen=True, slots=True)
class VentsSettings:
    supply_fan_speed_1: int | None = None
    supply_fan_speed_2: int | None = None
    supply_fan_speed_3: int | None = None
    exhaust_fan_speed_1: int | None = None
    exhaust_fan_speed_2: int | None = None
    exhaust_fan_speed_3: int | None = None

    @classmethod
    def from_values(cls, values: Values) -> Self:
        return cls().updated(values)

    def updated(self, values: Values) -> Self:
        return replace(
            self,
            supply_fan_speed_1=_convert(
                int, values.get("supply_fan_speed_1", self.supply_fan_speed_1)
            ),
            supply_fan_speed_2=_convert(
                int, values.get("supply_fan_speed_2", self.supply_fan_speed_2)
            ),
            supply_fan_speed_3=_convert(
                int, values.get("supply_fan_speed_3", self.supply_fan_speed_3)
            ),
            exhaust_fan_speed_1=_convert(
                int, values.get("exhaust_fan_speed_1", self.exhaust_fan_speed_1)
            ),
            exhaust_fan_speed_2=_convert(
                int, values.get("exhaust_fan_speed_2", self.exhaust_fan_speed_2)
            ),
            exhaust_fan_speed_3=_convert(
                int, values.get("exhaust_fan_speed_3", self.exhaust_fan_speed_3)
            ),
        )
