import asyncio
from typing import Any, cast

import pytest

from synapse_p2p import Node
from synapse_p2p.mdns import SERVICE_TYPE, MdnsDiscovery


class FakeInfo:
    def __init__(self, *, properties, addresses=None, port=9999):
        self.properties = properties
        self.port = port
        self._addresses = ["127.0.0.1"] if addresses is None else addresses

    def parsed_addresses(self):
        return self._addresses


@pytest.mark.asyncio
async def test_mdns_filters_to_same_swarm_and_team():
    node = Node(
        name="alpha",
        swarm="foo.electron.network",
        team="foo",
        mdns=True,
        heartbeat_interval=None,
    )
    discovery = MdnsDiscovery(node)

    peer = discovery._peer_from_service(
        cast(
            Any,
            FakeInfo(
                properties={
                    b"id": b"beta",
                    b"name": b"beta",
                    b"kind": b"node",
                    b"swarm": b"foo.electron.network",
                    b"team": b"foo",
                    b"capabilities": b"review,python",
                },
                port=1234,
            ),
        )
    )

    assert peer is not None
    assert peer.id == "beta"
    assert peer.name == "beta"
    assert peer.address == "127.0.0.1"
    assert peer.port == 1234
    assert peer.swarm == "foo.electron.network"
    assert peer.team == "foo"
    assert peer.capabilities == ["review", "python"]


@pytest.mark.asyncio
async def test_mdns_discovered_peer_is_added_when_membership_matches():
    node = Node(swarm="foo.electron.network", team="foo", mdns=True, heartbeat_interval=None)
    discovery = MdnsDiscovery(node)

    class FakeZeroconf:
        async def async_get_service_info(self, service_type, name, timeout=1000):
            return FakeInfo(
                properties={
                    b"id": b"beta",
                    b"name": b"beta",
                    b"kind": b"node",
                    b"swarm": b"foo.electron.network",
                    b"team": b"foo",
                    b"capabilities": b"",
                }
            )

    discovery.zeroconf = cast(Any, FakeZeroconf())

    await discovery._add_or_update_peer(SERVICE_TYPE, "beta._synapse._tcp.local.")

    assert "beta" in node.peers
    assert node.peers["beta"].name == "beta"


@pytest.mark.asyncio
async def test_mdns_discovered_peer_is_ignored_when_swarm_differs():
    node = Node(swarm="foo.electron.network", team="foo", mdns=True, heartbeat_interval=None)
    discovery = MdnsDiscovery(node)

    class FakeZeroconf:
        async def async_get_service_info(self, service_type, name, timeout=1000):
            return FakeInfo(
                properties={
                    b"id": b"beta",
                    b"name": b"beta",
                    b"kind": b"node",
                    b"swarm": b"bar.electron.network",
                    b"team": b"foo",
                    b"capabilities": b"",
                }
            )

    discovery.zeroconf = cast(Any, FakeZeroconf())

    await discovery._add_or_update_peer(SERVICE_TYPE, "beta._synapse._tcp.local.")

    assert node.peers == {}


def test_mdns_peer_from_service_requires_id_address_and_port():
    node = Node(swarm="foo.electron.network", mdns=True, heartbeat_interval=None)
    discovery = MdnsDiscovery(node)

    missing_id = FakeInfo(properties={b"swarm": b"foo.electron.network"})
    missing_address = FakeInfo(
        properties={b"id": b"beta", b"swarm": b"foo.electron.network"},
        addresses=[],
    )
    missing_port = FakeInfo(
        properties={b"id": b"beta", b"swarm": b"foo.electron.network"},
        port=None,
    )

    assert discovery._peer_from_service(cast(Any, missing_id)) is None
    assert discovery._peer_from_service(cast(Any, missing_address)) is None
    assert discovery._peer_from_service(cast(Any, missing_port)) is None


@pytest.mark.asyncio
async def test_mdns_ignores_self_advertisements():
    node = Node(
        node_id="self",
        swarm="foo.electron.network",
        mdns=True,
        heartbeat_interval=None,
    )
    discovery = MdnsDiscovery(node)

    class FakeZeroconf:
        async def async_get_service_info(self, service_type, name, timeout=1000):
            return FakeInfo(
                properties={
                    b"id": b"self",
                    b"name": b"self",
                    b"kind": b"node",
                    b"swarm": b"foo.electron.network",
                    b"team": b"default",
                    b"capabilities": b"",
                }
            )

    discovery.zeroconf = cast(Any, FakeZeroconf())

    await discovery._add_or_update_peer(SERVICE_TYPE, "self._synapse._tcp.local.")

    assert node.peers == {}


def test_mdns_callback_accepts_zeroconf_keyword_arguments():
    node = Node(swarm="foo.electron.network", mdns=True, heartbeat_interval=None)
    discovery = MdnsDiscovery(node)

    discovery._on_service_state_change(
        zeroconf=object(),
        service_type=SERVICE_TYPE,
        name="beta._synapse._tcp.local.",
        state_change=cast(Any, object()),
    )

    assert node.peers == {}


@pytest.mark.asyncio
async def test_node_join_starts_mdns_discovery_without_seeds():
    node = Node(mdns=True, heartbeat_interval=None)
    started = asyncio.Event()

    class FakeDiscovery:
        async def discover(self):
            started.set()

        async def stop(self):
            pass

    node.mdns = cast(Any, FakeDiscovery())

    await node.join()

    assert started.is_set()
