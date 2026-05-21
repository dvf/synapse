import pytest

from synapse_p2p import Client, Node
from synapse_p2p.types import Peer


@pytest.mark.asyncio
async def test_client_from_peer_calls_peer_endpoint():
    node = Node(name="worker", address="127.0.0.1", heartbeat_interval=None)

    @node.endpoint("hello")
    async def hello() -> str:
        return "world"

    tcp = await node.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        peer = Peer(id="worker", name="worker", address=host, port=port)
        assert await Client.from_peer(peer).call("hello") == "world"
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_client_peers_returns_peer_dataclasses():
    node = Node(address="127.0.0.1", heartbeat_interval=None)
    node.add_peer(Peer(id="worker", name="worker", address="127.0.0.1", port=9999))
    tcp = await node.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        peers = await Client(host, port).peers()
        assert peers == [node.peers["worker"]]
        assert peers[0].name == "worker"
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_client_peers_rejects_invalid_response():
    node = Node(address="127.0.0.1", heartbeat_interval=None)

    @node.endpoint("_synapse.peers", publish=False)
    async def peers_override():
        return {"not": "a list"}

    tcp = await node.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        with pytest.raises(RuntimeError, match="invalid peer list"):
            await Client(host, port).peers()
    finally:
        await node.stop()
