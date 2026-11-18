from aiovents import FanSpeed, Mode, VentsSettings, VentsStatus


def test_status_conversion_and_partial_update():
    current = VentsStatus.from_values(
        {
            "power_on": False,
            "mode": 1,
            "speed": 2,
            "supply_in_temperature": -10.0,
            "filter_timer_countdown": b"\x01\x02\x09\xff",
        }
    )
    assert current.power_on is False
    assert current.mode is Mode.HEATING
    assert current.speed is FanSpeed.MEDIUM
    assert current.supply_in_temperature == -10.0
    assert current.filter_days_remaining == 9
    assert current.fan1_speed is None
    updated = current.updated({"power_on": True, "mode": 9, "speed": None})
    assert updated.power_on is True
    assert updated.mode is None
    assert updated.speed is None
    assert updated.filter_days_remaining == 9
    assert current.mode is Mode.HEATING


def test_settings_merge_preserves_other_setpoints():
    settings = VentsSettings.from_values({"supply_fan_speed_1": 35})
    updated = settings.updated({"exhaust_fan_speed_3": 70})
    assert updated.supply_fan_speed_1 == 35
    assert updated.exhaust_fan_speed_3 == 70
    assert settings.exhaust_fan_speed_3 is None
