import asyncio
import socket

import pytest

from aiovents import AsyncVents, FanSpeed, Mode, VentsConnectionError, VentsValueError
from aiovents.registers import FILTER_TIMER_RESET, POWER_ON, SPEED, TARGET_TEMP

from .wire import DEVICE, reply

LOOPBACK = "127.0.0.1"


class Peer(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None
        self.requests = asyncio.Queue()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.requests.put_nowait((data, addr))

    async def receive(self, payload):
        frame, addr = await asyncio.wait_for(self.requests.get(), 1)
        assert frame[:4] == bytes.fromhex("fd fd 03 10")
        assert frame[4:20] == DEVICE
        assert frame[25:-2] == bytes.fromhex(payload)
        assert frame[-2:] == sum(frame[2:-2]).to_bytes(2, "little")
        return addr

    def send(self, addr, body, **kwargs):
        self.transport.sendto(reply(bytes.fromhex(body), **kwargs), addr)


async def open_peer():
    return await asyncio.get_running_loop().create_datagram_endpoint(
        Peer, local_addr=(LOOPBACK, 0)
    )


@pytest.fixture
async def peer():
    transport, peer = await open_peer()
    try:
        yield peer
    finally:
        transport.close()


@pytest.fixture
async def client(peer):
    port = peer.transport.get_extra_info("sockname")[1]
    async with AsyncVents(LOOPBACK, DEVICE.decode(), port=port, timeout=0.2) as client:
        yield client


async def test_waits_for_exact_keys_and_accepts_another_port(client, peer):
    task = asyncio.create_task(client.async_read_registers([POWER_ON, SPEED]))
    addr = await peer.receive("01 01 02")
    peer.send(addr, "01 01")
    peer.send(addr, "01 01 02 03 18 14")
    peer.send(addr, "01 01 02 03", device=b"1111111111111111")
    client._protocol.datagram_received(
        reply(bytes.fromhex("01 01 02 03")), ("192.0.2.10", 4000)
    )
    other_transport, other_peer = await open_peer()
    try:
        other_peer.send(addr, "01 00 fc 03 fd 02")
        assert await task == {"power_on": False, "speed": None}
    finally:
        other_transport.close()


async def test_batches_status_and_settings_using_the_device_registers(client, peer):
    request = asyncio.create_task(client.async_get_status())
    addr = await peer.receive("01 01 0e 02 18 21 1e 1f 22 25 4a 4b 06 83 88 64")
    peer.send(
        addr,
        "01 01 0e 02 02 03 18 16 fe 02 21 9c ff fd 1e fe 02 1f d7 00 "
        "fe 02 22 32 00 25 2d fe 02 4a e2 04 fe 02 4b 4c 04 06 00 83 01 88 00 "
        "fe 04 64 0a 02 1e 00",
    )
    status = await request
    assert status.mode is Mode.COOLING
    assert status.speed is FanSpeed.HIGH
    assert status.supply_in_temperature == -10.0
    assert status.supply_out_temperature is None
    assert status.exhaust_in_temperature == 21.5
    assert status.current_humidity == 45
    assert status.fan1_speed == 1250
    assert status.filter_days_remaining == 30

    request = asyncio.create_task(client.async_get_settings())
    addr = await peer.receive("01 3a 3c 3e 3b 3d 3f")
    peer.send(addr, "3a 19 3b 1e 3c 2d 3d 32 3e 41 3f 46")
    settings = await request
    assert settings.supply_fan_speed_3 == 65
    assert settings.exhaust_fan_speed_1 == 30


async def test_superset_never_satisfies_request(client, peer):
    task = asyncio.create_task(client.async_read_register(POWER_ON))
    addr = await peer.receive("01 01")
    peer.send(addr, "01 01 02 03")
    with pytest.raises(VentsConnectionError, match="matching response"):
        await task


async def test_stale_buffered_datagrams_are_drained(client, peer):
    task = asyncio.create_task(client.async_read_register(POWER_ON))
    addr = await peer.receive("01 01")
    peer.send(addr, "01 01")
    assert await task is True
    client._protocol.datagram_received(reply(b"\x01\x01"), addr=(LOOPBACK, 4000))
    task = asyncio.create_task(client.async_read_register(POWER_ON))
    addr = await peer.receive("01 01")
    peer.send(addr, "01 00")
    assert await task is False


async def test_confirmed_write_returns_without_readback(client, peer):
    task = asyncio.create_task(client.async_write_register(TARGET_TEMP, 23))
    addr = await peer.receive("03 18 17")
    peer.send(addr, "18 17")
    assert await task == 23
    assert peer.requests.empty()


@pytest.mark.parametrize("echo", ["18 15", "fd 18", None])
async def test_unconfirmed_write_reads_back_before_other_calls(client, peer, echo):
    task = asyncio.create_task(client.async_write_register(TARGET_TEMP, 23))
    write_addr = await peer.receive("03 18 17")
    other = asyncio.create_task(client.async_read_register(POWER_ON))
    if echo is not None:
        peer.send(write_addr, echo)
    addr = await peer.receive("01 18")
    assert not other.done()
    peer.send(write_addr, "18 17")
    peer.send(addr, "18 16")
    assert await task == 22
    addr = await peer.receive("01 01")
    peer.send(addr, "01 01")
    assert await other is True


async def test_filter_reset_is_two_ordered_unacknowledged_writes(client, peer):
    await asyncio.wait_for(client.async_reset_filter(), 0.5)
    await peer.receive("02 65 01")
    await peer.receive("02 80 01")
    with pytest.raises(VentsValueError, match="write-only"):
        await client.async_read_register(FILTER_TIMER_RESET)
    assert peer.requests.empty()


async def test_success_resets_timeouts_before_hostname_is_resolved_again(
    peer, monkeypatch
):
    lookups = []
    port = peer.transport.get_extra_info("sockname")[1]

    async def resolve(host, port, *, family, type):
        assert family == socket.AF_INET
        assert type == socket.SOCK_DGRAM
        lookups.append(host)
        return [(family, type, socket.IPPROTO_UDP, "", (LOOPBACK, port))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    async with AsyncVents(
        "vents-ahu.example", DEVICE.decode(), port=port, timeout=0.05
    ) as client:
        for misses in (2, 3):
            for _ in range(misses):
                task = asyncio.create_task(client.async_read_register(POWER_ON))
                await peer.receive("01 01")
                with pytest.raises(VentsConnectionError):
                    await task
            assert len(lookups) == (1 if misses == 2 else 2)
            task = asyncio.create_task(client.async_read_register(POWER_ON))
            addr = await peer.receive("01 01")
            peer.send(addr, "01 01")
            assert await task is True


async def test_cancelled_read_cannot_supply_next_read_of_same_register(client, peer):
    first = asyncio.create_task(client.async_read_register(POWER_ON))
    abandoned_addr = await peer.receive("01 01")
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    second = asyncio.create_task(client.async_read_register(POWER_ON))
    addr = await peer.receive("01 01")
    peer.send(abandoned_addr, "01 00")
    peer.send(addr, "01 01")
    assert await second is True


async def test_endpoint_recovers_after_loss_and_close_is_idempotent(client, peer):
    task = asyncio.create_task(client.async_read_register(POWER_ON))
    await peer.receive("01 01")
    client._transport.close()
    with pytest.raises(VentsConnectionError, match="closed"):
        await task
    task = asyncio.create_task(client.async_read_register(POWER_ON))
    addr = await peer.receive("01 01")
    peer.send(addr, "01 01")
    assert await task is True
    transport = client._transport
    await client.async_close()
    await client.async_close()
    assert transport.is_closing()


async def test_hostname_resolution_times_out(monkeypatch):
    async def resolve(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    async with AsyncVents("vents-ahu.example", DEVICE.decode(), timeout=0.02) as client:
        async with asyncio.timeout(1):
            with pytest.raises(VentsConnectionError, match="Timed out resolving"):
                await client.async_read_register(POWER_ON)
