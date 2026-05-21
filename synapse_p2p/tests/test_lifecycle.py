import asyncio

import pytest

from synapse_p2p import Client, Node
from synapse_p2p.types import Peer


@pytest.mark.asyncio
async def test_join_emits_peer_joined_event():
    node = Node(swarm="foo.electron.network", team="foo", heartbeat_interval=None)
    joined = asyncio.Event()
    seen: list[Peer] = []

    @node.on("peer.joined")
    async def peer_joined(peer: Peer) -> None:
        seen.append(peer)
        joined.set()

    tcp = await node.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        await Client(host, port).call(
            "_synapse.join",
            {
                "id": "agent-1",
                "address": "127.0.0.1",
                "port": 9999,
                "swarm": "foo.electron.network",
                "team": "foo",
            },
        )
        await asyncio.wait_for(joined.wait(), 0.1)
        assert seen[0].id == "agent-1"
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_heartbeat_updates_last_seen_and_emits_event():
    node = Node(swarm="foo.electron.network", team="foo", heartbeat_interval=None)
    heartbeats = asyncio.Event()

    @node.on("peer.heartbeat")
    async def peer_heartbeat(peer: Peer) -> None:
        if peer.id == "agent-1":
            heartbeats.set()

    old_peer = Peer(
        id="agent-1",
        address="127.0.0.1",
        port=9999,
        swarm="foo.electron.network",
        team="foo",
        last_seen=1.0,
    )
    node.peers[old_peer.id] = old_peer
    tcp = await node.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        await Client(host, port).call(
            "_synapse.heartbeat",
            {
                "id": "agent-1",
                "address": "127.0.0.1",
                "port": 9999,
                "swarm": "foo.electron.network",
                "team": "foo",
            },
        )
        await asyncio.wait_for(heartbeats.wait(), 0.1)
        assert node.peers["agent-1"].last_seen > 1.0
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_stale_peer_emits_offline_and_is_removed():
    node = Node(heartbeat_interval=None, peer_timeout=0.01)
    offline = asyncio.Event()
    seen: list[Peer] = []

    @node.on("peer.offline")
    async def peer_offline(peer: Peer) -> None:
        seen.append(peer)
        offline.set()

    node.peers["stale"] = Peer(
        id="stale",
        address="127.0.0.1",
        port=9999,
        last_seen=1.0,
    )

    await node._reap_stale_peers()
    await asyncio.wait_for(offline.wait(), 0.1)

    assert "stale" not in node.peers
    assert seen[0].id == "stale"


@pytest.mark.asyncio
async def test_joined_nodes_exchange_heartbeats():
    bootstrap = Node(
        name="bootstrap",
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
        heartbeat_interval=0.01,
        peer_timeout=1,
    )
    tcp = await bootstrap.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    agent = Node(
        name="worker",
        role="worker",
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
        seeds=[(host, port)],
        heartbeat_interval=0.01,
        peer_timeout=1,
    )
    agent_tcp = await agent.start()

    try:
        await agent.join()
        await asyncio.sleep(0.05)
        assert agent.node_id in bootstrap.peers
        assert bootstrap.node_id in agent.peers
        assert bootstrap.peers[agent.node_id].port == agent_tcp.sockets[0].getsockname()[1]
    finally:
        await agent.stop()
        await bootstrap.stop()
