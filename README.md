# aiovents

[![PyPI version](https://img.shields.io/pypi/v/aiovents)](https://pypi.org/project/aiovents/)
[![Python versions](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB)](https://pypi.org/project/aiovents/)
[![Latest GitHub release](https://img.shields.io/github/v/release/voluzi/aiovents)](https://github.com/voluzi/aiovents/releases/latest)
[![CI](https://github.com/voluzi/aiovents/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/voluzi/aiovents/actions/workflows/ci.yml)
[![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A typed asyncio client for Vents and Blauberg air handling units on a local
network. Read operating data and fan settings in batches, write individual
registers, and reset the filter counter.

## Install

```sh
python -m pip install aiovents
```

## Quick start

Set `VENTS_HOST`, `VENTS_DEVICE_ID`, and `VENTS_PASSWORD` in your environment.

```python
import asyncio
import os

from aiovents import AsyncVents, VentsStatus


async def read_unit() -> VentsStatus:
    async with AsyncVents(
        os.environ["VENTS_HOST"],
        os.environ["VENTS_DEVICE_ID"],
        password=os.environ["VENTS_PASSWORD"],
    ) as unit:
        return await unit.async_get_status()


status = asyncio.run(read_unit())
print(f"Exhaust inlet temperature: {status.exhaust_in_temperature} °C")
print(f"Filter days remaining: {status.filter_days_remaining}")
```

## API

| API | Purpose |
| --- | --- |
| `AsyncVents(host, device_id, *, port=4000, password=..., timeout=1.5)` | Create a UDP client. The timeout is in seconds. Omit the password only when the unit uses the protocol default. |
| `async_get_status()` | Read a `VentsStatus` snapshot with power, mode, speeds, temperatures, humidity, alarms, and filter status. |
| `async_get_settings()` | Read a `VentsSettings` snapshot with three supply fan and three exhaust fan settings. |
| `async_read_register(register)`, `async_read_registers(registers)` | Read one register or a batch of registers defined in [`aiovents.registers`](src/aiovents/registers.py). |
| `async_write_register(register, value)` | Validate a write and return the confirmed value, which can differ from the request. |
| `async_trigger(register)` | Send a supported trigger. |
| `async_reset_filter()` | Send both filter reset triggers. The unit does not acknowledge them; check the next status read. |
| `async_close()` | Release the UDP socket. The async context manager also closes it. |

Unsupported or unreadable register values are `None`. Temperatures are in
degrees Celsius and the filter countdown is in days. Writes are checked
against the unit's reply or by reading the register back, including when
the write reply times out.

## Errors

| Error | Meaning |
| --- | --- |
| `VentsError` | Base class for client and protocol errors |
| `VentsConnectionError` | The device could not be reached or no valid reply arrived |
| `VentsValueError` | Invalid device credential, register, or requested value; also a `ValueError` |

## Compatibility

Requires Python **3.11 or later** and has no runtime dependencies. CI tests
Python 3.11, 3.12, and 3.13. The package includes type information.

Use a controller and firmware that implement the Vents AHU UDP register
protocol. A Vents or Blauberg model name alone does not establish
compatibility. The device ID must contain 1–16 ASCII characters; the client
pads shorter IDs on the right with zeroes. Credentials are sent without
encryption, so keep the UDP service on your local network.

The client serializes traffic and accepts matching replies from the unit's
address regardless of source port. It refreshes DNS after three consecutive
request failures.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and test instructions,
[CHANGELOG.md](CHANGELOG.md) for release notes, and [SECURITY.md](SECURITY.md)
for private vulnerability reporting.

## License

[MIT](LICENSE).
