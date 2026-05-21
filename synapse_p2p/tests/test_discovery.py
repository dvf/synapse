import pytest

from synapse_p2p import Client, Node, NodeKind
from synapse_p2p.types import Peer


def test_node_defaults_to_default_team():
    assert Node().team == "default"
    assert Node().self_peer().team == "default"


@pytest.mark.asyncio
async def test_synapse_info_and_peers_include_swarm_and_team():
    node = Node(
        name="bootstrap",
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
    )
    tcp = await node.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        info = await Client(host, port).call("_synapse.info")
        assert isinstance(info, dict)
        assert info["name"] == "bootstrap"
        assert info["kind"] == NodeKind.NODE.value
        assert info["swarm"] == "foo.electron.network"
        assert info["team"] == "foo"
        peers = await Client(host, port).call("_synapse.peers")
        assert peers == []
    finally:
        await node.stop()


@pytest.mark.asyncio
async def test_join_adds_peer_and_returns_known_peers_in_swarm_team():
    bootstrap = Node(
        name="bootstrap",
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
    )
    bootstrap.add_peer(
        Peer(
            id="known",
            address="127.0.0.1",
            port=9998,
            swarm="foo.electron.network",
            team="foo",
            name="known",
        )
    )
    tcp = await bootstrap.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        response = await Client(host, port).call(
            "_synapse.join",
            {
                "id": "joining",
                "address": "127.0.0.1",
                "port": 9999,
                "swarm": "foo.electron.network",
                "team": "foo",
                "name": "joining",
                "kind": "node",
                "capabilities": ["python"],
                "last_seen": 1.0,
            },
        )
        assert isinstance(response, dict)
        assert response["accepted"] is True
        assert {peer["id"] for peer in response["peers"]} == {"known", "joining"}
        assert "joining" in bootstrap.peers
    finally:
        await bootstrap.stop()


@pytest.mark.asyncio
async def test_join_uses_seeds_and_imports_peers():
    bootstrap = Node(
        name="bootstrap",
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
    )
    bootstrap.add_peer(
        Peer(
            id="known",
            address="127.0.0.1",
            port=9998,
            swarm="foo.electron.network",
            team="foo",
            name="known",
        )
    )
    tcp = await bootstrap.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    agent = Node(
        name="coder",
        role="coder",
        capabilities=["python"],
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
        seeds=[f"{host}:{port}"],
    )

    try:
        await agent.start()
        await agent.join()
        assert "known" in agent.peers
        assert bootstrap.node_id in agent.peers
        assert any(peer.name == "coder" for peer in bootstrap.peers.values())
    finally:
        await agent.stop()
        await bootstrap.stop()


@pytest.mark.asyncio
async def test_join_rejects_different_swarm():
    bootstrap = Node(
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
    )
    tcp = await bootstrap.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        with pytest.raises(RuntimeError, match="different swarm"):
            await Client(host, port).call(
                "_synapse.join",
                {
                    "id": "intruder",
                    "address": "127.0.0.1",
                    "port": 9999,
                    "swarm": "bar.electron.network",
                    "team": "foo",
                },
            )
    finally:
        await bootstrap.stop()


@pytest.mark.asyncio
async def test_join_rejects_different_team():
    bootstrap = Node(
        swarm="foo.electron.network",
        team="foo",
        address="127.0.0.1",
    )
    tcp = await bootstrap.start()
    host, port = tcp.sockets[0].getsockname()[:2]

    try:
        with pytest.raises(RuntimeError, match="different team"):
            await Client(host, port).call(
                "_synapse.join",
                {
                    "id": "intruder",
                    "address": "127.0.0.1",
                    "port": 9999,
                    "swarm": "foo.electron.network",
                    "team": "bar",
                },
            )
    finally:
        await bootstrap.stop()
