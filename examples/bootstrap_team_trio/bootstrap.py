import asyncio

from synapse_p2p import Node, NodeKind, Peer

bootstrap = Node(
    name="bootstrap",
    kind=NodeKind.BOOTSTRAP,
    swarm="foo.electron.network",
    port=9000,
    heartbeat_interval=5,
    peer_timeout=20,
)


@bootstrap.on("peer.joined")
async def peer_joined(peer: Peer) -> None:
    print(f"joined: {peer.name} ({peer.kind}) at {peer.address}:{peer.port}")


@bootstrap.on("peer.heartbeat")
async def peer_heartbeat(peer: Peer) -> None:
    print(f"heartbeat: {peer.name} at {peer.address}:{peer.port}")


@bootstrap.on("peer.offline")
async def peer_offline(peer: Peer) -> None:
    print(f"offline: {peer.name} ({peer.id})")


async def main() -> None:
    await bootstrap.start()
    try:
        print(f"bootstrap listening on {bootstrap.address}:{bootstrap.port}")
        await asyncio.Event().wait()
    finally:
        await bootstrap.stop()


if __name__ == "__main__":
    asyncio.run(main())
