import asyncio

from examples.pydantic_ai_team.common import SWARM
from synapse_p2p import Node, NodeKind, Peer

node = Node(
    name="team-seed",
    kind=NodeKind.BOOTSTRAP,
    swarm=SWARM,
    port=9100,
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"joined: {peer.name} @ {peer.address}:{peer.port} caps={peer.capabilities}")


async def main() -> None:
    await node.start()
    print(f"seed online for {SWARM} at {node.address}:{node.port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
