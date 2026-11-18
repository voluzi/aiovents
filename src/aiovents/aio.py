"""Async client for the Vents AHU UDP protocol."""

import asyncio
import logging
import socket
from collections import deque
from collections.abc import Sequence
from types import TracebackType
from typing import Self

from .codec import (
    RegisterKey,
    RegisterValue,
    Reply,
    build_body,
    build_frame,
    decode_reply,
    encode_password,
    encode_write,
    extract_inner,
    format_value,
    normalize_device_id,
    register_name,
    trigger_body,
)
from .const import (
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    PARAMETER_READ,
    PARAMETER_WRITE,
    PARAMETER_WRITE_WITH_RESPONSE,
)
from .exceptions import VentsConnectionError, VentsError, VentsValueError
from .models import SETTINGS_REGISTERS, STATUS_REGISTERS, VentsSettings, VentsStatus
from .registers import FILTER_TIMER_RESET, RESET_ALARMS, Register

_LOGGER = logging.getLogger(__name__)
_DNS_REFRESH_FAILURES = 3


class _ReplyTimeout(VentsConnectionError):
    """No matching reply arrived before the deadline."""


class _VentsDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.datagrams: deque[tuple[bytes, tuple[str, int]]] = deque(maxlen=64)
        self.ready = asyncio.Event()
        self.lost = False
        self.errors = 0

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.datagrams.append((data, addr))
        self.ready.set()

    def error_received(self, exc: Exception) -> None:
        self.errors += 1
        _LOGGER.debug("UDP transport reported an error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        self.lost = True
        self.ready.set()

    def drain(self) -> None:
        self.datagrams.clear()
        self.ready.clear()
        self.errors = 0

    async def receive(self) -> tuple[bytes, tuple[str, int]]:
        while not self.datagrams:
            if self.lost:
                raise OSError("UDP transport closed")
            self.ready.clear()
            await self.ready.wait()
        return self.datagrams.popleft()


class AsyncVents:
    """Serialize batched reads, writes and triggers on a lazy UDP transport."""

    def __init__(
        self,
        host: str,
        device_id: str,
        *,
        port: int = DEFAULT_PORT,
        password: str = DEFAULT_PASSWORD,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._device_id = normalize_device_id(device_id)
        self._device_bytes = self._device_id.encode("ascii")
        self._password = encode_password(password)
        self._address: str | None = None
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _VentsDatagramProtocol | None = None
        self._lock = asyncio.Lock()
        self._consecutive_failures = 0

    @property
    def device_id(self) -> str:
        return self._device_id

    async def _resolve_host(self) -> str:
        try:
            async with asyncio.timeout(self._timeout * 2):
                addresses = await asyncio.get_running_loop().getaddrinfo(
                    self._host,
                    self._port,
                    family=socket.AF_INET,
                    type=socket.SOCK_DGRAM,
                )
            return str(addresses[0][4][0])
        except TimeoutError as exc:
            raise VentsConnectionError("Timed out resolving device address") from exc
        except (OSError, IndexError) as exc:
            raise VentsConnectionError(f"Cannot resolve device address: {exc}") from exc

    async def _endpoint(
        self,
    ) -> tuple[asyncio.DatagramTransport, _VentsDatagramProtocol]:
        if (
            self._transport is None
            or self._transport.is_closing()
            or self._protocol is None
            or self._protocol.lost
        ):
            self._close_endpoint()
            (
                self._transport,
                self._protocol,
            ) = await asyncio.get_running_loop().create_datagram_endpoint(
                _VentsDatagramProtocol,
                local_addr=("0.0.0.0", 0),
                family=socket.AF_INET,
            )
        return self._transport, self._protocol

    def _close_endpoint(self) -> None:
        if self._transport is not None:
            self._transport.close()
        self._transport = None
        self._protocol = None

    async def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= _DNS_REFRESH_FAILURES:
            self._consecutive_failures = 0
            try:
                self._address = await self._resolve_host()
            except VentsConnectionError as exc:
                _LOGGER.warning("Cannot refresh device address: %s", exc)

    async def _send(self, function: bytes, body: bytes) -> _VentsDatagramProtocol:
        if self._address is None:
            self._address = await self._resolve_host()
        transport, protocol = await self._endpoint()
        protocol.drain()
        frame = build_frame(self._device_bytes, self._password, function, body)
        transport.sendto(frame, (self._address, self._port))
        return protocol

    async def _request(
        self, function: bytes, body: bytes, expected: set[RegisterKey]
    ) -> Reply:
        discarded = 0
        try:
            protocol = await self._send(function, body)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + self._timeout
            try:
                async with asyncio.timeout_at(deadline):
                    while loop.time() < deadline:
                        data, sender = await protocol.receive()
                        if sender[0] == self._address:
                            try:
                                values = decode_reply(
                                    extract_inner(data), self._device_bytes
                                )
                            except VentsError as exc:
                                _LOGGER.debug("Discarding invalid response: %s", exc)
                            else:
                                if values.keys() == expected:
                                    self._consecutive_failures = 0
                                    return values
                        discarded += 1
            except TimeoutError:
                pass
        except OSError as exc:
            self._close_endpoint()
            await self._record_failure()
            raise VentsConnectionError(f"Device request failed: {exc}") from exc
        except asyncio.CancelledError:
            self._close_endpoint()
            raise

        # A late reply to the old socket has no request ID to distinguish it.
        self._close_endpoint()
        await self._record_failure()
        _LOGGER.debug(
            "Timed out waiting for a matching response; discarded %d datagrams"
            " and received %d transport errors",
            discarded,
            protocol.errors,
        )
        raise _ReplyTimeout("Timed out waiting for a matching response")

    async def _read_locked(
        self, regs: Sequence[Register]
    ) -> dict[str, RegisterValue | None]:
        if not regs:
            return {}
        for reg in regs:
            if reg.get("write_only"):
                raise VentsValueError(f"Register '{register_name(reg)}' is write-only")

        body, expected = build_body([reg["parameter"] for reg in regs])
        values = await self._request(PARAMETER_READ, body, expected)
        out: dict[str, RegisterValue | None] = {}
        for reg in regs:
            page, parameter = reg["parameter"]
            raw = values[page, parameter]
            name = register_name(reg)
            out[name] = None
            if raw is not None:
                try:
                    out[name] = format_value(reg, raw)
                except VentsError as exc:
                    _LOGGER.warning("Ignoring invalid register value: %s", exc)
        return out

    async def async_read_registers(
        self, regs: Sequence[Register]
    ) -> dict[str, RegisterValue | None]:
        """Read a complete register batch; unsupported registers have value None."""
        async with self._lock:
            return await self._read_locked(regs)

    async def async_read_register(self, reg: Register) -> RegisterValue | None:
        return (await self.async_read_registers([reg]))[register_name(reg)]

    async def async_write_register(
        self, reg: Register, value: RegisterValue
    ) -> RegisterValue:
        """Write a compact value and return the device's confirmed value."""
        encoded = encode_write(reg, value)
        body, expected = build_body([reg["parameter"]], encoded)
        async with self._lock:
            try:
                values = await self._request(
                    PARAMETER_WRITE_WITH_RESPONSE, body, expected
                )
            except _ReplyTimeout:
                echo = None
            else:
                page, parameter = reg["parameter"]
                echo = values[page, parameter]
            if echo == bytes([encoded]):
                return format_value(reg, echo)

            name = register_name(reg)
            _LOGGER.warning("Unconfirmed write echo for %s; reading back", name)
            self._close_endpoint()
            confirmed = (await self._read_locked([reg]))[name]
            if confirmed is None:
                raise VentsError(f"Cannot confirm write for register '{name}'")
            return confirmed

    async def _trigger_locked(self, reg: Register) -> None:
        try:
            await self._send(PARAMETER_WRITE, trigger_body(reg))
        except OSError as exc:
            self._close_endpoint()
            await self._record_failure()
            raise VentsConnectionError(f"Device trigger failed: {exc}") from exc

    async def async_trigger(self, reg: Register) -> None:
        """Send a write-only trigger without waiting for a reply."""
        async with self._lock:
            await self._trigger_locked(reg)

    async def async_reset_filter(self) -> None:
        """Restart the filter countdown and clear the associated alarm."""
        async with self._lock:
            await self._trigger_locked(FILTER_TIMER_RESET)
            await self._trigger_locked(RESET_ALARMS)

    async def async_get_status(self) -> VentsStatus:
        return VentsStatus.from_values(
            await self.async_read_registers(STATUS_REGISTERS)
        )

    async def async_get_settings(self) -> VentsSettings:
        return VentsSettings.from_values(
            await self.async_read_registers(SETTINGS_REGISTERS)
        )

    async def async_close(self) -> None:
        """Release the socket and cached address."""
        async with self._lock:
            self._close_endpoint()
            self._address = None
            self._consecutive_failures = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.async_close()
