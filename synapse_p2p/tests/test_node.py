import asyncio

import pytest

from synapse_p2p.client import Client
from synapse_p2p.framing import read_frame, write_frame
from synapse_p2p.messages import RemoteProcedureCall, RPCError, RPCRequest, RPCResponse
from synapse_p2p.node import Node
from synapse_p2p.serializers import MessagePackRPCSerializer


def test_endpoint_decorator_registers(node):
    @node.endpoint("sum")
    async def _sum(a, b, **kwargs):
        return a + b

    assert "sum" in node.endpoint_directory


def test_endpoint_decorator_uses_function_name_by_default(node):
    @node.endpoint()
    async def ping(**kwargs):
        return None

    assert "ping" in node.endpoint_directory


def test_background_decorator_registers_task(node):
    @node.background(5)
    async def heartbeat():
        pass

    task = next(task for task in node.background_executor.tasks if task.name == "heartbeat")
    assert task.period == 5


async def _send_message(node: Node, message) -> RPCResponse:
    tcp = await asyncio.start_server(node.handle_data, node.address, node.port)
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


async def _send_rpc(node: Node, rpc: RemoteProcedureCall) -> RPCResponse:
    return await _send_message(node, rpc)


@pytest.mark.asyncio
async def test_node_round_trip_over_tcp():
    node = Node(address="127.0.0.1")

    @node.endpoint("sum")
    async def _sum(a, b):
        return a + b

    response = await _send_rpc(node, RPCRequest(id="abc", endpoint="sum", args=[2, 3]))
    assert response == RPCResponse(id="abc", ok=True, result=5)


@pytest.mark.asyncio
async def test_client_call_over_tcp():
    node = Node(address="127.0.0.1")

    @node.endpoint("sum")
    async def _sum(a, b, scale=1):
        return (a + b) * scale

    tcp = await asyncio.start_server(node.handle_data, node.address, node.port)
    host, port = tcp.sockets[0].getsockname()[:2]

    async with tcp:
        result = await Client(host, port).call("sum", 2, 3, scale=2)

    assert result == 10


@pytest.mark.asyncio
async def test_unknown_endpoint_responds_bad_request():
    node = Node(address="127.0.0.1")
    response = await _send_rpc(node, RPCRequest(id="abc", endpoint="nope"))
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"


@pytest.mark.asyncio
async def test_endpoint_exception_responds_internal_error_without_killing_node():
    node = Node(address="127.0.0.1")

    @node.endpoint("boom")
    async def boom(**kwargs):
        raise RuntimeError("kaboom")

    response = await _send_rpc(node, RPCRequest(id="abc", endpoint="boom"))
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "internal_error"


@pytest.mark.asyncio
async def test_node_injects_rpc_and_connection_when_requested():
    node = Node(address="127.0.0.1")

    @node.endpoint("inspect")
    async def inspect_context(rpc, connection):
        return {"request_id": rpc.id, "connection_id_length": len(connection.identifier)}

    response = await _send_rpc(node, RPCRequest(id="abc", endpoint="inspect"))
    assert response.ok is True
    assert response.result == {"request_id": "abc", "connection_id_length": 8}


@pytest.mark.asyncio
async def test_node_rejects_response_sent_as_request():
    node = Node(address="127.0.0.1")
    response = await _send_message(node, RPCResponse(id="abc", ok=True, result="wrong-way"))
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"


@pytest.mark.asyncio
async def test_client_raises_on_rpc_error():
    node = Node(address="127.0.0.1")

    tcp = await asyncio.start_server(node.handle_data, node.address, node.port)
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


@pytest.mark.asyncio
async def test_node_start_and_stop_lifecycle():
    node = Node(address="127.0.0.1")

    @node.endpoint("ping")
    async def ping():
        return "pong"

    tcp = await node.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    assert await Client(host, port).call("ping") == "pong"

    await node.stop()
    assert node._listener is None


def test_response_error_shape():
    response = RPCResponse(id="abc", ok=False, error=RPCError("code", "message"))
    assert response.error is not None
    assert response.error.code == "code"
