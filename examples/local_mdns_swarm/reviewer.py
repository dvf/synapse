import asyncio

from synapse_p2p import Broadcast, Node, Peer

node = Node(
    name="reviewer",
    role="reviewer",
    swarm="foo.electron.network",
    capabilities=["code-review"],
    mdns=True,
)


@node.on("peer.joined")
async def joined(peer: Peer) -> None:
    print(f"joined: {peer.name} at {peer.address}:{peer.port}")


@node.endpoint("team.question")
async def answer(question: str, broadcast: Broadcast) -> dict:
    await node.reply(broadcast, {"from": node.name, "answer": "I can review it."})
    return {"accepted": True}


async def main() -> None:
    await node.start()
    await node.join()
    print(f"reviewer online at {node.address}:{node.port}")
    print("waiting for local Synapse nodes...")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
