# aiovents

An asyncio UDP client for Vents and Blauberg air handling units that use the Vents AHU protocol.
It requires Python 3.11 or newer and has no runtime dependencies.

## Usage

```python
import asyncio

from aiovents import AsyncVents, VentsStatus


async def read_status() -> VentsStatus:
    async with AsyncVents(
        "vents-ahu.example",
        "0000000000000000",
        password="example-password",
    ) as client:
        return await client.async_get_status()


status = asyncio.run(read_status())
```

The default UDP port is 4000 and the reply timeout is 1.5 seconds. The device ID must
contain 1 to 16 ASCII characters; IDs shorter than 16 characters are padded on the right
with zeroes. Supply the unit's configured password; omitting it uses the protocol default.

`async_get_status()` and `async_get_settings()` each read one batch. Unsupported or unreadable
values are `None`. Temperatures are signed Celsius values, and the filter countdown is in days.
For individual registers, use `async_read_register()` or `async_read_registers()` with definitions
from `aiovents.registers`.

Writes are verified against the device echo or by reading back the register. For example,
`await client.async_write_register(SPEED, FanSpeed.LOW)` requests low fan speed and returns
the confirmed value, which can differ from the request. `SPEED` is available from
`aiovents.registers`, and `FanSpeed` from `aiovents`.

`async_reset_filter()` sends two unacknowledged triggers; read the status to check whether
the countdown reset. The client serializes operations, accepts matching replies from the unit's
IP regardless of source port, and refreshes DNS after three consecutive request failures.
An unreachable device raises `VentsConnectionError`. The async context manager releases the
UDP socket.

## Development

```sh
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy --strict src
pytest -q
python -m build
```

The tests use synthetic frames and loopback UDP peers.

MIT license.
