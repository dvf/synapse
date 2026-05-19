import asyncio

import pytest

from synapse_p2p.client import Client
from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.messages import RemoteProcedureCall, RPCError, RPCRequest, RPCResponse
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


async def _send_message(server: Server, message) -> RPCResponse:
    tcp = await asyncio.start_server(server.handle_data, server.address, server.port)
    host, port = tcp.sockets[0].getsockname()[:2]

    async with tcp:
        reader, writer = await asyncio.open_connection(host, port)
        await write_frame(writer, MessagePackRPCSerializer.serialize(message))
        data = await read_frame(reader, 4096)
        writer.close()
        await writer.wait_closed()

    response = MessagePackRPCSerializer.deserialize(data)
    assert isinstance(response, RPCResponse)
    return response


async def _send_rpc(server: Server, rpc: RemoteProcedureCall) -> RPCResponse:
    return await _send_message(server, rpc)


@pytest.mark.asyncio
async def test_server_round_trip_over_tcp():
    server = Server(address="127.0.0.1", port=0)

    @server.endpoint("sum")
    async def _sum(a, b):
        return a + b

    response = await _send_rpc(server, RPCRequest(id="abc", endpoint="sum", args=[2, 3]))
    assert response == RPCResponse(id="abc", ok=True, result=5)


@pytest.mark.asyncio
async def test_client_call_over_tcp():
    server = Server(address="127.0.0.1", port=0)

    @server.endpoint("sum")
    async def _sum(a, b, scale=1):
        return (a + b) * scale

    tcp = await asyncio.start_server(server.handle_data, server.address, server.port)
    host, port = tcp.sockets[0].getsockname()[:2]

    async with tcp:
        result = await Client(host, port).call("sum", 2, 3, scale=2)

    assert result == 10


@pytest.mark.asyncio
async def test_unknown_endpoint_responds_bad_request():
    server = Server(address="127.0.0.1", port=0)
    response = await _send_rpc(server, RPCRequest(id="abc", endpoint="nope"))
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"


@pytest.mark.asyncio
async def test_endpoint_exception_responds_internal_error_without_killing_server():
    server = Server(address="127.0.0.1", port=0)

    @server.endpoint("boom")
    async def boom(**kwargs):
        raise RuntimeError("kaboom")

    response = await _send_rpc(server, RPCRequest(id="abc", endpoint="boom"))
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "internal_error"


@pytest.mark.asyncio
async def test_server_injects_rpc_and_node_when_requested():
    server = Server(address="127.0.0.1", port=0)

    @server.endpoint("inspect")
    async def inspect_context(rpc, node):
        return {"request_id": rpc.id, "node_id_length": len(node.identifier)}

    response = await _send_rpc(server, RPCRequest(id="abc", endpoint="inspect"))
    assert response.ok is True
    assert response.result == {"request_id": "abc", "node_id_length": 8}


@pytest.mark.asyncio
async def test_server_rejects_response_sent_as_request():
    server = Server(address="127.0.0.1", port=0)
    response = await _send_message(server, RPCResponse(id="abc", ok=True, result="wrong-way"))
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"


@pytest.mark.asyncio
async def test_client_raises_on_rpc_error():
    server = Server(address="127.0.0.1", port=0)

    tcp = await asyncio.start_server(server.handle_data, server.address, server.port)
    host, port = tcp.sockets[0].getsockname()[:2]

    async with tcp:
        with pytest.raises(RuntimeError, match="Unregistered endpoint"):
            await Client(host, port).call("missing")


@pytest.mark.asyncio
async def test_client_raises_on_non_response_payload():
    async def handle(reader, writer):
        await read_frame(reader, 4096)
        await write_frame(
            writer,
            MessagePackRPCSerializer.serialize(RPCRequest(id="abc", endpoint="not-response")),
        )
        writer.close()
        await writer.wait_closed()

    tcp = await asyncio.start_server(handle, "127.0.0.1", 0)
    host, port = tcp.sockets[0].getsockname()[:2]

    async with tcp:
        with pytest.raises(RuntimeError, match="non-response"):
            await Client(host, port).call("anything")


@pytest.mark.asyncio
async def test_client_timeout():
    async def handle(reader, writer):
        await read_frame(reader, 4096)
        await asyncio.sleep(0.05)
        writer.close()
        await writer.wait_closed()

    tcp = await asyncio.start_server(handle, "127.0.0.1", 0)
    host, port = tcp.sockets[0].getsockname()[:2]

    async with tcp:
        with pytest.raises(TimeoutError):
            await Client(host, port, timeout=0.01).call("slow")


def test_response_error_shape():
    response = RPCResponse(id="abc", ok=False, error=RPCError("code", "message"))
    assert response.error is not None
    assert response.error.code == "code"
