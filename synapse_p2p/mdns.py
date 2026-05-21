import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from synapse_p2p.types import Peer

if TYPE_CHECKING:
    from synapse_p2p.node import Node

SERVICE_TYPE = "_synapse._tcp.local."


def _encode(value: str | None) -> bytes:
    return (value or "").encode()


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return value


def _service_label(node: "Node") -> str:
    label = node.name or node.node_id[:8]
    safe = "".join(ch if ch.isalnum() or ch in "-" else "-" for ch in label).strip("-")
    return safe or node.node_id[:8]


class MdnsDiscovery:
    """Advertise and discover Synapse nodes on the local network with mDNS."""

    def __init__(self, node: "Node") -> None:
        self.node = node
        self.zeroconf: AsyncZeroconf | None = None
        self.browser: AsyncServiceBrowser | None = None
        self.service_info: AsyncServiceInfo | None = None

    async def start(self) -> None:
        if self.zeroconf is not None:
            return

        self.zeroconf = AsyncZeroconf()
        self.service_info = self._service_info()
        await self.zeroconf.async_register_service(
            self.service_info,
            allow_name_change=True,
        )
        self.browser = AsyncServiceBrowser(
            self.zeroconf.zeroconf,
            SERVICE_TYPE,
            handlers=[self._on_service_state_change],
            delay=0,
        )

    async def stop(self) -> None:
        if self.zeroconf is None:
            return
        if self.service_info is not None:
            await self.zeroconf.async_unregister_service(self.service_info)
        await self.zeroconf.async_close()
        self.zeroconf = None
        self.browser = None
        self.service_info = None

    async def discover(self, wait: float = 0) -> None:
        if self.zeroconf is None:
            await self.start()
        if wait > 0:
            await asyncio.sleep(wait)

    def _service_info(self) -> AsyncServiceInfo:
        name = f"{_service_label(self.node)}-{self.node.node_id[:8]}.{SERVICE_TYPE}"
        return AsyncServiceInfo(
            SERVICE_TYPE,
            name,
            port=self.node.port,
            properties={
                "id": _encode(self.node.node_id),
                "name": _encode(self.node.name),
                "kind": _encode(self.node.kind.value),
                "swarm": _encode(self.node.swarm),
                "team": _encode(self.node.team),
                "capabilities": _encode(
                    ",".join(capability.name for capability in self.node.capabilities)
                ),
            },
            parsed_addresses=[self.node.address],
        )

    def _on_service_state_change(
        self,
        zeroconf: Any,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if state_change in {ServiceStateChange.Added, ServiceStateChange.Updated}:
            asyncio.create_task(self._add_or_update_peer(service_type, name))

    async def _add_or_update_peer(self, service_type: str, name: str) -> None:
        if self.zeroconf is None:
            return
        info = await self.zeroconf.async_get_service_info(service_type, name, timeout=1000)
        if info is None:
            return

        peer = self._peer_from_service(info)
        if peer is None or peer.id == self.node.node_id:
            return
        try:
            self.node._validate_peer_membership(peer)
        except Exception:
            return

        self.node.add_peer(peer)
        logger.debug("mDNS discovered peer {} @ {}:{}", peer.id, peer.address, peer.port)

    def _peer_from_service(self, info: AsyncServiceInfo) -> Peer | None:
        properties = info.properties or {}
        peer_id = _decode(properties.get(b"id"))
        swarm = _decode(properties.get(b"swarm")) or None
        team = _decode(properties.get(b"team")) or None
        if not peer_id:
            return None

        addresses = info.parsed_addresses()
        if not addresses:
            return None

        capabilities = [
            capability
            for capability in _decode(properties.get(b"capabilities")).split(",")
            if capability
        ]
        if info.port is None:
            return None

        return Peer(
            id=peer_id,
            name=_decode(properties.get(b"name")),
            kind=_decode(properties.get(b"kind")) or "node",
            address=addresses[0],
            port=info.port,
            swarm=swarm,
            team=team,
            capabilities=capabilities,
        )
