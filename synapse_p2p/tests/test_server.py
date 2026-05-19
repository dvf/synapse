import asyncio

import pytest

from synapse_p2p.messages import RemoteProcedureCall
from synapse_p2p.serializers import MessagePackRPCSerializer
from synapse_p2p.server import Server


def test_endpoint_decorator_registers(server):
    @server.endpoint("sum")
    async def _sum(a, b, **kwargs):
        return a + b

    assert "sum" in server.endpoint_directory


def test_endpoint_decorator_uses_function_name_by_default(server):
    @server.endpoint()
    async def ping(**kwargs):
        return None

    assert "ping" in server.endpoint_directory


def test_background_decorator_registers_task(server):
    @server.background(5)
    async def heartbeat():
        pass

    assert len(server.background_executor.tasks) == 1
    assert server.background_executor.tasks[0].name == "heartbeat"
    assert server.background_executor.tasks[0].period == 5


async def _send_rpc(server: Server, rpc: RemoteProcedureCall) -> bytes:
    tcp = await asyncio.start_server(server.handle_data, server.address, server.port)
    host, port = tcp.sockets[0].getsockname()[:2]

    async with tcp:
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(MessagePackRPCSerializer.serialize(rpc))
        await writer.drain()
        data = await reader.read(1024)
        writer.close()
        await writer.wait_closed()

    return data


@pytest.mark.asyncio
async def test_server_round_trip_over_tcp():
    server = Server(address="127.0.0.1", port=0)

    @server.endpoint("sum")
    async def _sum(a, b, response, **kwargs):
        response.write(f"{a + b}".encode())

    data = await _send_rpc(server, RemoteProcedureCall(endpoint="sum", args=[2, 3]))
    assert data == b"5"


@pytest.mark.asyncio
async def test_unknown_endpoint_responds_400():
    server = Server(address="127.0.0.1", port=0)
    data = await _send_rpc(server, RemoteProcedureCall(endpoint="nope"))
    assert data == b"400"


@pytest.mark.asyncio
async def test_endpoint_exception_responds_500_without_killing_server():
    server = Server(address="127.0.0.1", port=0)

    @server.endpoint("boom")
    async def boom(**kwargs):
        raise RuntimeError("kaboom")

    data = await _send_rpc(server, RemoteProcedureCall(endpoint="boom"))
    assert data == b"500"
